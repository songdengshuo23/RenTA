/** 精灵表加载器 — Spritesheet 处理旋转 + 统一 orig 去抖 */
import { Spritesheet, Assets, Rectangle } from 'pixi.js'

export async function loadSpritesheetFromUrl(jsonUrl) {
  const r = await fetch(jsonUrl)
  const data = await r.json()
  const base = jsonUrl.substring(0, jsonUrl.lastIndexOf('/') + 1)

  const img = data.meta?.image
  const url = (img && !img.includes('placeholder'))
    ? base + img
    : base + jsonUrl.split('/').pop().replace(/\.json$/, '')

  const atlas = await Assets.load(url)
  const ss = new Spritesheet(atlas, data)
  await ss.parse()


  return { textures: ss.textures, animations: ss.animations, meta: data.meta }
}
