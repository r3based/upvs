export const mode = process.env.NEXT_PUBLIC_MODE || 'api';
export const apiBase = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

export function apiUrl(path: string): string {
  if (mode === 'static') {
    return path;
  }
  return `${apiBase}${path}`;
}
