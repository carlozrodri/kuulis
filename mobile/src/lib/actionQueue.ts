import { api } from './api';
import { localFile } from './localFile';
import { createOutbox } from './outbox';

const FILE = 'outbox.json';

/** The app's queue of ride actions, chat messages and ratings (doc 20); see `outbox.ts`. */
export const outbox = createOutbox({
  send: (item) => api(item.path, { method: 'POST', body: item.body, headers: { 'Idempotency-Key': item.id } }),
  read: () => localFile.read(FILE),
  write: (contents) => localFile.write(FILE, contents),
});
