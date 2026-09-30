import { describe, expect, it, vi } from 'vitest'
import { droppedWishes, saveWithFollowups, undoCreated } from './saveFlow'

describe('uloženie po skene a Späť', () => {
  it('zlyhaný doplnok po uložení (kategória, kód) nevráti chybu uloženia', async () => {
    const onError = vi.fn()
    const ids = await saveWithFollowups(
      async () => [7, 8],
      [async () => {
        throw new Error('sieť')
      }, async () => {}],
      onError,
    )
    // Kusy vznikli: ďalší sken ich nesmie uložiť znova.
    expect(ids).toEqual([7, 8])
    expect(onError).toHaveBeenCalledOnce()
  })

  it('zlyhané samotné uloženie sa hlási ako chyba a doplnky nebežia', async () => {
    const follow = vi.fn()
    await expect(saveWithFollowups(async () => {
      throw new Error('server')
    }, [follow], vi.fn()))
      .rejects
      .toThrow('server')
    expect(follow).not.toHaveBeenCalled()
  })

  it('Späť zmaže práve tieto kusy a spočíta zlyhania', async () => {
    const removed: number[] = []
    const failed = await undoCreated([3, 4, 5], async id => {
      removed.push(id)
      return id !== 4
    })
    expect(removed).toEqual([3, 4, 5])
    expect(failed).toBe(1)
  })

  it('z odpovede vyberie položky Chcem, ktoré uloženie vyradilo', () => {
    const wish = (num: string) => ({
      catalog_num: num,
      name: num,
      target_price_eur: null,
      note: null,
      created_at: '2026-01-02T10:00:00',
    })
    const found = droppedWishes([
      { removed_from_wishlist: wish('71046-1') },
      { removed_from_wishlist: null },
      {},
      { removed_from_wishlist: wish('71046-3') },
    ])
    expect(found.map(w => w.catalog_num)).toEqual(['71046-1', '71046-3'])
  })
})
