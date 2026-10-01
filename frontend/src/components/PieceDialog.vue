<script setup lang="ts">
  import type { ItemCondition, ValuedItem } from '@/api/types'
  /**
   * Úprava jedného kusu. Opraviť sa dá všetko, čo sa zadáva pri pridaní,
   * lebo pomýliť sa je ľahké a inak by nezostalo než kus zmazať a založiť
   * odznova, čím by sa stratila jeho história.
   *
   * Aj kategórie, hoci visia na sete, nie na kuse: výber je ten istý ako
   * pri pridaní (CategoryPicker) a zapíše sa až pri uložení, takže Zrušiť
   * nezanechá nič. Chyba kategórie sa ohlási, úprava kusu sa uloží aj tak.
   *
   * Uloženie čaká na kategórie, preto sa dialóg počas neho nedá zavrieť
   * a udalosť nesie id kusu, pre ktorý sa začalo: rodič by inak mohol
   * zapísať úpravu na kus, ktorý je v dialógu medzitým.
   *
   * Udalosť nesie aj `done`: rodič ním povie výsledok. Pri chybe dialóg
   * ostane otvorený so zadanými úpravami a dá sa uložiť znova; kategórie,
   * ktoré sa už zapísali, sa druhýkrát neposielajú a dialóg povie, že
   * ostali uložené (Zrušiť ich nevráti). Zavrieť po úspechu je vec rodiča.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { CONDITIONS, FLAGS, PURPOSES, VARIANTS } from '@/api/types'
  import CategoryPicker from '@/components/CategoryPicker.vue'
  import CurrencySelect from '@/components/CurrencySelect.vue'
  import DateField from '@/components/DateField.vue'
  import PlaceFields from '@/components/PlaceFields.vue'
  import { useCategoryPicker } from '@/composables/useCategoryPicker'
  import { useEuroPreview } from '@/composables/useDisplayCurrency'
  import { foreignEntryOn } from '@/composables/useDisplayPrefs'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { type CurrencyCode, currencySymbol, isCurrency, toNumber } from '@/utils/format'
  import { purchaseChange } from '@/utils/priceEdit'

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{ item: ValuedItem | null, locations?: string[] }>()
  const emit = defineEmits<{
    'save': [id: number, payload: Record<string, unknown>, done: (ok: boolean) => void]
    'remove': [id: number]
    /** Zmenili sa kategórie setu (výber alebo správca); rodič obnoví ich zobrazenie. */
    'categories-changed': []
  }>()

  const { t } = useI18n()
  const notify = useNotifyStore()
  const categories = useCategoryPicker()

  const condition = ref<ItemCondition>('new_sealed')
  const variant = ref<string | null>(null)
  const flags = ref<string[]>([])
  const purpose = ref<string | null>(null)
  const location = ref<string | null>('')
  const box = ref<string | null>('')
  const price = ref('')
  /** Mena kúpy; v cudzej mene prepočíta eurá server kurzom zo dňa kúpy. */
  const currency = ref<CurrencyCode>('EUR')
  const date = ref('')
  const place = ref<string | null>('')
  const note = ref('')
  const saving = ref(false)
  const confirmRemove = ref(false)
  /** Úprava kusu sa neuložila, kategórie setu áno. */
  const categoriesKept = ref(false)

  /** Varianty ceny dávajú zmysel len pri minifigúrke. */
  const isMinifig = computed(() => props.item?.catalog.kind === 'minifig')

  const collection = useCollectionStore()
  /** Výber meny pri cene: zapnutý v Nastaveniach, alebo kus už je v cudzej mene. */
  const showCurrency = computed(() =>
    foreignEntryOn() || currency.value !== 'EUR' || isCurrency(props.item?.purchase_currency),
  )
  const preview = useEuroPreview(price, currency, date)

  watch(open, isOpen => {
    if (isOpen && collection.purchasePlaces.length === 0) collection.loadLocations()
    if (!isOpen || !props.item) return
    const item = props.item
    condition.value = item.condition
    variant.value = item.price_variant
    flags.value = [...(item.flags ?? [])]
    purpose.value = item.purpose ?? null
    location.value = item.location ?? ''
    box.value = item.box ?? ''
    // Kúpa v cudzej mene sa upravuje v nej, eurá sú len prepočet.
    currency.value = isCurrency(item.purchase_currency) ? item.purchase_currency : 'EUR'
    price.value = String(
      toNumber(currency.value === 'EUR' ? item.purchase_price_eur : item.purchase_price_original) ?? '',
    )
    date.value = item.purchase_date ?? ''
    place.value = item.purchase_place ?? ''
    note.value = item.note ?? ''
    saving.value = false
    confirmRemove.value = false
    categoriesKept.value = false
    categories.reset()
    // Chybu načítania ukáže výber sám (so Skúsiť znova), úprava kusu ide ďalej.
    categories.load(item.catalog_num)
  })

  function close (): void {
    open.value = false
  }

  /** Zapíše zmenený výber kategórií setu; bez zmeny nejde von nič. Vráti, či sa zapísal. */
  async function saveCategories (num: string): Promise<boolean> {
    if (!categories.dirty.value) return false
    let written = false
    const before = categories.changes.value.length
    try {
      written = (await categories.apply(num)) > 0
    } catch (error_) {
      // Časť kategórií sa mohla zapísať aj pri chybe: zmien potom ubudlo.
      written = categories.changes.value.length < before
      notify.error(error_, t('notice.categoriesFailed'))
    }
    emit('categories-changed')
    return written
  }

  async function save (): Promise<void> {
    if (!props.item || saving.value) return
    saving.value = true
    const { id, catalog_num: num } = props.item
    const payload = {
      condition: condition.value,
      price_variant: isMinifig.value ? variant.value : null,
      flags: flags.value,
      purpose: purpose.value,
      location: (location.value ?? '').trim() || null,
      // Prázdna krabica sa zmaže (server z prázdneho reťazca urobí null).
      box: (box.value ?? '').trim(),
      // Len zmenená cena; inak by sa zrušilo označenie doplnenej ceny.
      ...purchaseChange(
        {
          eur: props.item.purchase_price_eur,
          currency: props.item.purchase_currency,
          original: props.item.purchase_price_original,
        },
        currency.value,
        price.value,
      ),
      purchase_date: date.value || null,
      purchase_place: (place.value ?? '').trim() || null,
      note: note.value.trim() || null,
    }
    const written = await saveCategories(num)
    emit('save', id, payload, ok => {
      if (ok) return
      // Chybu ohlásil rodič; úpravy ostávajú v poliach.
      saving.value = false
      if (written) categoriesKept.value = true
    })
  }

  function remove (): void {
    if (!props.item || saving.value) return
    saving.value = true
    emit('remove', props.item.id)
  }
</script>

<template>
  <v-dialog v-model="open" max-width="680" :persistent="saving" scrollable>
    <v-card v-if="item">
      <v-card-title>{{ t('piece.title') }}</v-card-title>
      <v-card-subtitle>{{ item.catalog.name }} · {{ item.catalog_num }}</v-card-subtitle>

      <v-card-text class="d-flex flex-column ga-4 pt-4">
        <div>
          <div class="text-title-small mb-2">{{ t('piece.condition') }}</div>

          <v-chip-group v-model="condition" column mandatory selected-class="bg-primary">
            <v-chip
              v-for="value in CONDITIONS"
              :key="value"
              label
              :value="value"
              variant="outlined"
            >{{ t(`condition.${value}`) }}</v-chip>
          </v-chip-group>
        </div>

        <div v-if="isMinifig">
          <div class="text-title-small mb-2">{{ t('piece.variant') }}</div>

          <v-chip-group v-model="variant" column selected-class="bg-primary">
            <v-chip
              v-for="value in VARIANTS"
              :key="value"
              label
              :value="value"
              variant="outlined"
            >{{ t(`variant.${value}`) }}</v-chip>
          </v-chip-group>
        </div>

        <div>
          <div class="text-title-small mb-2">{{ t('piece.flags') }}</div>

          <v-chip-group v-model="flags" column multiple selected-class="bg-primary">
            <v-chip
              v-for="value in FLAGS"
              :key="value"
              label
              :value="value"
              variant="outlined"
            >{{ t(`flag.${value}`) }}</v-chip>
          </v-chip-group>
        </div>

        <div>
          <div class="text-title-small mb-2">{{ t('purpose.label') }}</div>

          <v-chip-group v-model="purpose" column selected-class="bg-primary">
            <v-chip
              v-for="value in PURPOSES"
              :key="value"
              label
              :value="value"
              variant="outlined"
            >{{ t(`purpose.${value}`) }}</v-chip>
          </v-chip-group>
        </div>

        <PlaceFields v-model:box="box" v-model:location="location" variant="outlined" />

        <div class="d-flex ga-3 flex-wrap">
          <CurrencySelect v-if="showCurrency" v-model="currency" variant="outlined" />

          <v-text-field
            v-model="price"
            :hide-details="!item.purchase_price_auto && !preview.text.value"
            :hint="item.purchase_price_auto ? t('purchaseAuto.dialogHint') : preview.text.value"
            :label="t('piece.price')"
            persistent-hint
            :prefix="currencySymbol(currency)"
            :prepend-inner-icon="item.purchase_price_auto ? 'mdi-auto-fix' : undefined"
            style="min-width: 140px"
            type="number"
            variant="outlined"
          />

          <DateField
            v-model="date"
            clearable
            hide-details
            :label="t('piece.date')"
            style="min-width: 160px"
          />
        </div>

        <v-combobox
          v-model="place"
          hide-details
          :items="collection.purchasePlaces"
          :label="t('piece.place')"
          prepend-inner-icon="mdi-storefront-outline"
        />

        <v-textarea
          v-model="note"
          hide-details
          :label="t('piece.note')"
          rows="2"
          variant="outlined"
        />

        <CategoryPicker
          :hint="t('piece.categoriesHint')"
          :label="t('piece.categories')"
          :picker="categories"
          title-class="text-title-small"
          @managed="emit('categories-changed')"
        />

        <!-- Kategórie sa zapisujú pred kusom; po chybe kusu ostali uložené. -->
        <v-alert
          v-if="categoriesKept"
          density="comfortable"
          type="info"
          variant="tonal"
        >
          {{ t('piece.categoriesKept') }}
        </v-alert>

        <v-alert
          v-if="confirmRemove"
          density="comfortable"
          type="warning"
          variant="tonal"
        >
          {{ t('piece.removeWarning') }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-btn
          v-if="!confirmRemove"
          color="negative"
          prepend-icon="mdi-delete-outline"
          variant="text"
          @click="confirmRemove = true"
        >{{ t('piece.remove') }}</v-btn>

        <v-btn
          v-else
          color="negative"
          :loading="saving"
          prepend-icon="mdi-delete"
          variant="flat"
          @click="remove"
        >{{ t('piece.removeConfirm') }}</v-btn>

        <v-spacer />
        <v-btn :disabled="saving" variant="text" @click="close">{{ t('common.cancel') }}</v-btn>

        <v-btn
          color="primary"
          :disabled="confirmRemove"
          :loading="saving"
          variant="flat"
          @click="save"
        >{{ t('common.save') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
