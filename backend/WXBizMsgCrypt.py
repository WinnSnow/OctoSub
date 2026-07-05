#!/usr/bin/env python
# -*- encoding:utf-8 -*-

import base64
import string
import random
import hashlib
import time
import struct
from Crypto.Cipher import AES
import xml.etree.cElementTree as ET
import socket
from pkcs7encoder import PKCS7Encoder

"""
关于Crypto.Cipher模块，ImportError: No module named 'Crypto'
解决方案：
pip uninstall crypto
pip uninstall pycrypto
pip install pycryptodome
"""

class FormatException(Exception):
    pass

def throw_exception(message, exception_class=FormatException):
    """my define raise exception function"""
    raise exception_class(message)

class WXBizMsgCrypt(object):
    #构造函数
    #@param sToken: 公众平台上，开发者设置的Token
    #@param sEncodingAESKey: 公众平台上，开发者设置的EncodingAESKey
    #@param sReceiveId: 不同场景含义不同，企业应用的回调，表示Corpid
    def __init__(self,sToken,sEncodingAESKey,sReceiveId):
        try:
            self.key = base64.b64decode(sEncodingAESKey+"=")
            assert len(self.key) == 32
        except Exception:
            throw_exception("[error]: EncodingAESKey unvalid !", FormatException)
            #return IOResponse.AES_KEY_INVALID,None
        self.m_sToken = sToken
        self.m_sReceiveId = sReceiveId
        #self.m_sCorpid = sCorpid
        self.iv = self.key[:16]


    def EncryptMsg(self, sReplyMsg, sNonce, timestamp=None):
        #sReplyMsg: 明文消息
        #sNonce: 随机串
        #timestamp: 时间戳
        #将明文消息转成bytes
        sReplyMsg = sReplyMsg.encode('utf-8')
        #1. 拼接
        text = self.get_random_str() + struct.pack("I",socket.htonl(len(sReplyMsg))) + sReplyMsg + self.m_sReceiveId.encode()
        #2. pkcs7补位
        pkcs7 = PKCS7Encoder()
        text = pkcs7.encode(text)
        #3. 加密
        cryptor = AES.new(self.key,AES.MODE_CBC,self.iv)
        try:
            ciphertext = cryptor.encrypt(text)
            # ciphertext: bytes
        except Exception:
            return -40006, None #加密失败
        #4. base64编码
        sEncryptBase64 = base64.b64encode(ciphertext)
        #sEncryptBase64: bytes
        sEncrypt = sEncryptBase64.decode('utf-8')

        if timestamp is None:
            timestamp = str(int(time.time()))
        # 生成签名
        sMsgSignature = self.get_signature(self.m_sToken, timestamp, sNonce, sEncrypt)

        # 生成发送的xml
        sResData = self.generate(sEncrypt, sMsgSignature, timestamp, sNonce)
        return 0, sResData

    def DecryptMsg(self, sPostData, sMsgSignature, sTimeStamp, sNonce):
        '''
        检验消息的真实性，并且获取解密后的明文.
        <xml>
            <ToUserName><![CDATA[toUser]]></ToUserName>
            <Encrypt><![CDATA[msg_encrypt]]></Encrypt>
        </xml>
        '''
        # 提取密文
        xml_tree = ET.fromstring(sPostData)
        sEncrypt = xml_tree.find("Encrypt").text

        # 效验签名
        sSignature = self.get_signature(self.m_sToken, sTimeStamp, sNonce, sEncrypt)
        if sSignature != sMsgSignature:
            return -40001, None #签名效验失败

        # 解密
        try:
            # sEncrypt: str
            ciphertext = base64.b64decode(sEncrypt)
            # ciphertext: bytes
            cryptor = AES.new(self.key,AES.MODE_CBC,self.iv)
            sPlain = cryptor.decrypt(ciphertext)
            # sPlain: bytes
        except Exception:
            return -40007,None #解密失败

        # pkcs7解码
        pkcs7 = PKCS7Encoder()
        sPlain = pkcs7.decode(sPlain)
        # sPlain: bytes

        # 提取明文
        sMsgContent,sReceiveId = self.get_msg_content_and_receiveid(sPlain)
        # sMsgContent: bytes
        # sReceiveId: bytes
        if self.m_sReceiveId != sReceiveId.decode('utf-8'):
            return -40005, None #receiveid效验失败

        return 0,sMsgContent.decode('utf-8')

    def get_random_str(self):
        """ 随机生成16位字符串
        @return: 16位字符串
        """
        #rule = string.ascii_letters + string.digits
        rule = string.ascii_lowercase + string.digits
        str = random.sample(rule, 16)
        return "".join(str).encode()

    def get_signature(self,sToken,sTimeStamp,sNonce,sEncrypt):
        # 字典序排序
        sortlist = [sToken, sTimeStamp, sNonce, sEncrypt]
        sortlist.sort()
        sSortString = "".join(sortlist)
        # sha1
        sha = hashlib.sha1()
        sha.update(sSortString.encode())
        return sha.hexdigest()

    def generate(self,sEncrypt,sMsgSignature,sTimeStamp,sNonce):
        resp_dict = {
            'Encrypt':sEncrypt,
            'MsgSignature':sMsgSignature,
            'TimeStamp':sTimeStamp,
            'Nonce':sNonce
        }
        resp_xml = self.dict_to_xml(resp_dict)
        return resp_xml

    def dict_to_xml(self,dict_data):
        xml = ["<xml>"]
        for k, v in dict_data.items():
            xml.append("<{0}><![CDATA[{1}]]></{0}>".format(k, v))
        xml.append("</xml>")
        return "".join(xml)

    def get_msg_content_and_receiveid(self,plain):
        # 4位msg长度
        sMsgLen = socket.ntohl(struct.unpack("I",plain[16:20])[0])
        # msg_content
        sMsgContent = plain[20:20+sMsgLen]
        # receiveid
        sReceiveId = plain[20+sMsgLen:]

        return sMsgContent,sReceiveId
