import { describe, expect, it, vi } from 'vitest'
import { saveWithFollowups, undoCreated } from './saveFlow'

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
})
