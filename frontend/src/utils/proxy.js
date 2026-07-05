export function parseProxyLink(link) {
  try {
    const urlStr = String(link || '').trim();
    if (!urlStr.includes('://')) return null;

    const url = new URL(urlStr);
    const protocolMap = {
      'socks5:': 'socks5',
      'socks4:': 'socks4',
      'http:': 'http',
      'https:': 'http',
    };
    const protocol = protocolMap[url.protocol] || 'socks5';
    const host = url.hostname;
    const port = url.port || (protocol === 'http' ? 8080 : 1080);
    const username = decodeURIComponent(url.username || '');
    const password = decodeURIComponent(url.password || '');
    return { protocol, host, port, username, password };
  } catch {
    return null;
  }
}
