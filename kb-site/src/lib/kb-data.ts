import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

// kb-site/src/lib → kb-site/src → kb-site → karpathy-kb → generated/
const GENERATED_DIR = join(
  dirname(fileURLToPath(import.meta.url)),
  '..',
  '..',
  '..',
  'generated'
);

function loadJson<T>(filename: string): T {
  const path = join(GENERATED_DIR, filename);
  return JSON.parse(readFileSync(path, 'utf-8')) as T;
}

export interface WikiJudgment {
  text: string;
  confidence: string;
  valid_until: string;
}

export interface WikiItem {
  slug: string;
  status: 'draft' | 'published';
  title: string;
  tags: string[];
  sources: string[];
  updated_at: string;
  judgments: WikiJudgment[];
}

export interface WikiIndex {
  generated_at: string;
  items: WikiItem[];
}

export interface RoleItem {
  role_id: string;
  display_name: string;
  focus_areas: string[];
}

export interface RoleIndex {
  generated_at: string;
  roles: RoleItem[];
}

export interface TodayItem {
  kind: 'aging_judgment' | 'unlinked_capture';
  id: string;
  title: string;
  judgment_text?: string;
  valid_until?: string;
  priority: 'high' | 'medium' | 'low';
  actions: string[];
}

export interface TodayIndex {
  generated_at: string;
  items: TodayItem[];
}

export function getWikiIndex(): WikiIndex {
  return loadJson<WikiIndex>('wiki-index.json');
}

export function getRoleIndex(): RoleIndex {
  return loadJson<RoleIndex>('role-index.json');
}

export function getTodayIndex(): TodayIndex {
  return loadJson<TodayIndex>('today-index.json');
}
