/** Skratky na typy z OpenAPI, aby sa komponenty nepísali cez celé cesty. */

import type { components } from './schema'

type S = components['schemas']

export type User = S['UserOut']
export type CatalogItem = S['CatalogOut']
export type CatalogDetail = S['CatalogDetailOut']
export type Ownership = S['OwnershipOut']
export type Item = S['ItemOut']
export type ValuedItem = S['ValuedItemOut']
export type GroupedItem = S['GroupedItemOut']
export type Summary = S['SummaryOut']
export type TimelinePoint = S['TimelinePointOut']
export type Mover = S['MoverOut']
export type SeriesProgress = S['SeriesProgressOut']
export type PriceOverview = S['PriceOverviewOut']
export type PriceCheck = S['PriceCheckOut']
export type SetImage = S['SetImageOut']
export type PricePoint = S['PricePointOut']
export type PriceDelta = S['PriceDeltaOut']
export type RefreshStatus = S['RefreshStatusOut']
export type ShareLink = S['ShareOut']
export type PublicCollection = S['PublicCollectionOut']
export type PublicItem = S['PublicItemOut']
export type WishlistItem = S['WishlistOut']
/** Položka Chcem, ktorú pridanie kusu vyradilo (na Späť). */
export type RemovedWish = S['RemovedWishOut']
export type ProviderStatus = S['ProviderStatusOut']
export type ApiKeys = S['ApiKeysOut']
export type Source = S['SourceOut']
export type SourceCapability = S['SourceCapabilityOut']
export type BreakdownRow = S['BreakdownRowOut']
export type SalesChannel = S['SalesChannelOut']
export type Photo = S['PhotoOut']
export type ItemPurpose = S['ItemPurpose']
export type Facets = S['FacetsOut']
export type SelectionTotals = S['SelectionTotalsOut']
export type ImportSummary = S['ImportSummaryOut']
export type ImportDetail = S['ImportOut']
export type ImportRow = S['ImportRowOut']
export type FacetOption = S['FacetOption']
export type Category = S['CategoryOut']
export type CategoryRule = S['CategoryRule']
export type CatalogCategory = S['CatalogCategoryOut']
export type SavedView = S['SavedViewOut']
export type Catalog = S['CatalogOut']
export type CmfSeries = S['CmfSeriesOut']
export type CmfMember = S['CmfMemberOut']
export type CmfSync = S['CmfSyncOut']
export type ThemeRow = S['ThemeOut']
export type ThemeYear = S['ThemeYearOut']
export type ThemeWave = S['ThemeWaveOut']
export type ApiKeysUpdate = S['ApiKeysUpdate']
export type ItemCondition = S['ItemCondition']
export type ItemStatus = S['ItemStatus']
export type PriceVariant = S['PriceVariant']

export const CONDITIONS: ItemCondition[] = [
  'new_sealed',
  'opened_unbuilt',
  'built',
  'parted_out',
]

export const FLAGS = [
  'has_box',
  'has_manual',
  'has_stand',
  'complete',
  'damaged_box',
  'missing_parts',
] as const

export type Flag = (typeof FLAGS)[number]

/** Na čo kus je. Umiestnenie hovorí kde, zoznam hovorí prečo. */
export const PURPOSES: ItemPurpose[] = ['investment', 'for_sale', 'display', 'build']

/** Podoby minifigúrky. Pri setoch sa nepoužívajú. */
export const VARIANTS: PriceVariant[] = ['sealed', 'complete', 'figure_only']

/** Príznaky, ktoré znižujú hodnotu, sa v rozhraní kreslia inak. */
export const NEGATIVE_FLAGS: readonly string[] = ['damaged_box', 'missing_parts']
