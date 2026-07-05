#!/usr/bin/env python
# -*- encoding:utf-8 -*-


class PKCS7Encoder(object):
    """提供基于PKCS7算法的加解密接口"""

    block_size = 32
    def encode(self, text):
        """
        对需要加密的明文进行填充补位
        @param text: 需要进行填充补位操作的明文
        @return: 补齐明文
        """
        text_length = len(text)
        # 计算需要填充的位数
        amount_to_pad = self.block_size - (text_length % self.block_size)
        if amount_to_pad == 0:
            amount_to_pad = self.block_size
        # 获得补位所用的字符
        pad = chr(amount_to_pad).encode()
        return text + pad * amount_to_pad

    def decode(self, decrypted):
        """
        删除解密后明文的补位字符
        @param decrypted: 解密后的明文
        @return: 删除补位字符后的明文
        """
        pad = ord(decrypted[-1:])
        if pad<1 or pad > 32:
            pad = 0
        return decrypted[:-pad]
