import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const { id } = req.query;
  const dataDir = process.env.DATA_DERIVED_DIR || '/app/data/derived';
  const filePath = path.join(dataDir, 'page_bundles', `${id}.json`);

  if (!fs.existsSync(filePath)) {
    res.status(404).json({ error: 'bundle не найден' });
    return;
  }

  const raw = fs.readFileSync(filePath, 'utf-8');
  const data = JSON.parse(raw);
  res.status(200).json(data);
}
