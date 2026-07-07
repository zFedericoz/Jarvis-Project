export function _md(s: string) {
  return s
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.+?)\*/g, '<i>$1</i>')
    .replace(/`(.+?)`/g, '<code style="background:rgba(0,0,0,0.3);border-radius:2px;padding:0 3px;font-size:0.9em">$1</code>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#00e5ff;text-decoration:underline">$1</a>');
}
