<script setup lang="ts">
  import type { CatalogDetail, PriceOverview, ValuedItem } from '@/api/types'
  /**
   * Návrh ceny a text inzerátu pre Aukro alebo Bazoš.
   *
   * Cena je trhová cena pre stav kusu, pri rozbalenom aj s rozpätím, ak ho
   * zdroj dáva. Nič sa k nej nepripočítava ani neodpočítava: prirážky za
   * krabicu či zľavy za chýbajúci návod by boli vymyslené čísla.
   * Text je po slovensky bez ohľadu na jazyk appky, lebo ide na slovenské
   * trhoviská.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { money, toNumber } from '@/utils/format'

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{
    item: ValuedItem | null
    catalog: CatalogDetail | null
    pricesNew: PriceOverview | null
    pricesUsed: PriceOverview | null
  }>()

  const { t } = useI18n()

  const CONDITION_SK: Record<string, string> = {
    new_sealed: 'nový, nerozbalený v krabici',
    opened_unbuilt: 'rozbalený, nepostavený',
    built: 'postavený',
    parted_out: 'rozobraný',
  }

  const sealed = computed(() => props.item?.condition === 'new_sealed')

  /** Cena pre stav kusu; keď chýba, z druhého stavu s poznámkou. */
  const quote = computed(() => {
    const own = sealed.value ? props.pricesNew : props.pricesUsed
    const other = sealed.value ? props.pricesUsed : props.pricesNew
    if (own?.current?.avg_price) {
      return { source: own, approx: false }
    }
    if (other?.current?.avg_price) {
      return { source: other, approx: true }
    }
    return null
  })

  const suggested = computed(() => {
    const value = toNumber(quote.value?.source.current?.avg_price)
    return value === null ? null : Math.round(value)
  })

  const range = computed(() => {
    const current = quote.value?.source.current
    const low = toNumber(current?.min_price)
    const high = toNumber(current?.max_price)
    if (low === null || high === null || low === high) return null
    return { low, high }
  })

  const priceNote = computed(() => {
    if (!quote.value) return t('listing.noPrice')
    if (quote.value.approx) return t('listing.priceApprox')
    return sealed.value ? t('listing.priceNew') : t('listing.priceUsed')
  })

  const price = ref('')

  function buildText (): string {
    const item = props.item
    const catalog = props.catalog
    if (!item || !catalog) return ''
    const flags = new Set(item.flags)
    const lines: string[] = []

    const title = ['LEGO', catalog.theme, catalog.catalog_num.replace(/-1$/, ''), catalog.name]
      .filter(Boolean)
      .join(' ')
    lines.push(title, '', `Stav: ${CONDITION_SK[item.condition] ?? item.condition}.`)

    const included = [
      flags.has('has_box') && 'krabica',
      flags.has('has_manual') && 'návod',
      flags.has('has_stand') && 'stojan',
    ].filter(Boolean)
    if (included.length > 0) lines.push(`Obsahuje: ${included.join(', ')}.`)
    if (flags.has('complete')) lines.push('Set je kompletný.')

    const defects = [
      flags.has('damaged_box') && 'poškodená krabica',
      flags.has('missing_parts') && 'chýbajú niektoré dieliky',
    ].filter(Boolean)
    if (defects.length > 0) lines.push(`Na vedomie: ${defects.join(', ')}.`)

    const facts = [
      catalog.num_parts && `${catalog.num_parts} dielikov`,
      catalog.year && `rok vydania ${catalog.year}`,
    ].filter(Boolean)
    if (facts.length > 0) lines.push(`${facts.join(', ')}.`.replace(/^./, c => c.toUpperCase()))
    // Presný dátum má prednosť pred rokom, rovnako ako v hlavičke detailu.
    const retiredYear = catalog.retired_date?.slice(0, 4) ?? catalog.retired_at
    if (retiredYear) lines.push(`Už sa nevyrába, stiahnutý z predaja v roku ${retiredYear}.`)
    if (item.note) lines.push('', item.note)

    const value = toNumber(price.value)
    if (value !== null) lines.push('', `Cena: ${money(value, { decimals: 0 })}`)
    return lines.join('\n')
  }

  const text = ref('')
  const copied = ref(false)

  watch(open, isOpen => {
    if (!isOpen) return
    copied.value = false
    price.value = suggested.value === null ? '' : String(suggested.value)
    text.value = buildText()
  })

  watch(price, () => {
    if (open.value) text.value = buildText()
  })

  async function copy (): Promise<void> {
    try {
      await navigator.clipboard.writeText(text.value)
      copied.value = true
    } catch {
      // Schránka ide len cez https alebo localhost. Inak aspoň označíme text,
      // nech sa dá skopírovať ručne.
      const area = document.querySelector<HTMLTextAreaElement>('.listing-text textarea')
      area?.select()
    }
  }
</script>

<template>
  <v-dialog v-model="open" max-width="620" scrollable>
    <v-card v-if="item && catalog">
      <v-card-title>{{ t('listing.title') }}</v-card-title>
      <v-card-subtitle>{{ catalog.name }} · {{ catalog.catalog_num }}</v-card-subtitle>

      <v-card-text class="d-flex flex-column ga-3 pt-4">
        <div class="d-flex ga-3 align-start flex-wrap">
          <v-text-field
            v-model="price"
            hide-details
            :label="t('listing.price')"
            prefix="€"
            style="max-width: 180px"
            type="number"
            variant="outlined"
          />

          <div class="text-caption text-medium-emphasis pt-2" style="flex: 1; min-width: 200px">
            <div>{{ priceNote }}</div>

            <div v-if="range">
              {{ t('listing.range', { low: money(range.low, { decimals: 0 }), high: money(range.high, { decimals: 0 }) }) }}
            </div>
          </div>
        </div>

        <v-textarea
          v-model="text"
          auto-grow
          class="listing-text"
          hide-details
          :label="t('listing.text')"
          rows="8"
          variant="outlined"
        />
      </v-card-text>

      <v-card-actions>
        <v-btn
          :color="copied ? 'positive' : 'primary'"
          :prepend-icon="copied ? 'mdi-check' : 'mdi-content-copy'"
          variant="flat"
          @click="copy"
        >{{ copied ? t('listing.copied') : t('listing.copy') }}</v-btn>

        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
