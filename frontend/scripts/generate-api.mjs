/**
 * Vygeneruje TypeScript typy z OpenAPI schémy backendu.
 *
 * Predpona /api/v1 sa z ciest odstráni, lebo ju už nesie baseUrl klienta.
 * Bez toho by sa v kóde písalo api.GET('/api/v1/items') a zároveň by sa
 * predpona pridala druhýkrát.
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

import openapiTS, { astToString } from 'openapi-typescript'

const PREFIX = '/api/v1'
const SOURCE = resolve('openapi.json')
const OUTPUT = resolve('src/api/schema.d.ts')

if (!existsSync(SOURCE)) {
  console.error(
    'Chýba openapi.json. Najprv ho vyexportuj z backendu:\n'
    + '  cd ../backend && uv run python -m lego_api.openapi_export',
  )
  // eslint-disable-next-line unicorn/no-process-exit -- toto je príkaz do terminálu
  process.exit(1)
}

const schema = JSON.parse(readFileSync(SOURCE, 'utf8'))
const paths = {}
let stripped = 0

for (const [path, value] of Object.entries(schema.paths ?? {})) {
  if (path.startsWith(PREFIX)) {
    paths[path.slice(PREFIX.length) || '/'] = value
    stripped += 1
  } else {
    paths[path] = value
  }
}

schema.paths = paths
schema.servers = [{ url: PREFIX }]

const ast = await openapiTS(schema)
const header = '/* Vygenerované z OpenAPI. Needituj ručne, spusti `npm run gen:api`. */\n'
writeFileSync(OUTPUT, header + astToString(ast), 'utf8')

console.log(`Hotovo: ${OUTPUT}. Ciest bez predpony: ${stripped}.`)
