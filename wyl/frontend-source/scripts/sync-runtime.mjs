import { cp, copyFile, mkdir, rm } from 'node:fs/promises'
import { dirname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const sourceRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const distRoot = resolve(sourceRoot, 'dist')
const runtimeRoot = resolve(sourceRoot, '..', 'frontend')

if (!runtimeRoot.endsWith(`${sep}wyl${sep}frontend`)) {
  throw new Error(`Refusing to sync outside the frontend runtime: ${runtimeRoot}`)
}

await rm(resolve(runtimeRoot, 'assets'), { recursive: true, force: true })
await cp(resolve(distRoot, 'assets'), resolve(runtimeRoot, 'assets'), { recursive: true })
await copyFile(resolve(distRoot, 'index.html'), resolve(runtimeRoot, 'index.html'))
await copyFile(resolve(distRoot, 'background.png'), resolve(runtimeRoot, 'background.png'))
await copyFile(resolve(distRoot, 'renta-logo-mark.png'), resolve(runtimeRoot, 'renta-logo-mark.png'))
await mkdir(resolve(runtimeRoot, 'icons'), { recursive: true })
await cp(resolve(distRoot, 'icons'), resolve(runtimeRoot, 'icons'), { recursive: true, force: true })

console.log(`Synced frontend runtime to ${runtimeRoot}`)
