import { esc } from './ui.js';
const inline = s => esc(s).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/`([^`]+)`/g, '<code>$1</code>');

export function mdToHtml(md) {
  const lines = md.split('\n');
  let out = '', i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith('```')) {
      const buf = []; i++;
      while (i < lines.length && !lines[i].startsWith('```')) buf.push(lines[i++]);
      i++; out += `<pre>${esc(buf.join('\n'))}</pre>`; continue;
    }
    if (l.startsWith('### ')) { out += `<h3>${inline(l.slice(4))}</h3>`; i++; continue; }
    if (l.startsWith('## ')) { out += `<h2>${inline(l.slice(3))}</h2>`; i++; continue; }
    if (l.startsWith('# ')) { out += `<h1>${inline(l.slice(2))}</h1>`; i++; continue; }
    if (l.startsWith('> ')) {
      const q = [];
      while (i < lines.length && lines[i].startsWith('> ')) q.push(inline(lines[i++].slice(2)));
      out += `<blockquote>${q.join('<br>')}</blockquote>`; continue;
    }
    if (l.startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith('|')) rows.push(lines[i++]);
      const cells = r => r.split('|').slice(1, -1).map(c => inline(c.trim()));
      out += '<table><thead><tr>' + cells(rows[0]).map(c => `<th>${c}</th>`).join('') +
        '</tr></thead><tbody>' + rows.slice(2).map(r => '<tr>' + cells(r).map(c => `<td>${c}</td>`).join('') + '</tr>').join('') + '</tbody></table>';
      continue;
    }
    if (l.startsWith('- ')) {
      const li = [];
      while (i < lines.length && lines[i].startsWith('- ')) li.push(`<li>${inline(lines[i++].slice(2))}</li>`);
      out += `<ul>${li.join('')}</ul>`; continue;
    }
    if (l.trim() === '') { i++; continue; }
    out += `<p>${inline(l)}</p>`; i++;
  }
  return out;
}