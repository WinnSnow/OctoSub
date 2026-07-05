export function normalizeSearchResult(item) {
  const links = item.links || [];
  return {
    ...item,
    links,
    resource_url: item.resource_url || links[0]?.url || '',
    link_types: item.link_types || [...new Set(links.map(link => link.type || 'others'))],
  };
}
