<script setup lang="ts">
  import type { Catalog, ItemCondition } from '@/api/types'
  /**
   * „Kúpil som“: pridá do zbierky vec, ktorú appka už pozná, bez hľadania.
   *
   * Otvára sa z Chcem aj z chýbajúcej figúrky. Pýta sa len na to, čo sa pri
   * kúpe naozaj vie (počet, stav, cena, dátum, kde); zvyšok sa dá doplniť
   * v detaile. Keď vec bola v Chcem, po uložení odtiaľ zmizne, aj keď sa
   * kupovala z inej obrazovky: vyradí ju server pri každom pridaní kusu
   * (`POST /items`), dialóg ju nemaže.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import { CONDITIONS } from '@/api/types'
  import CurrencySelect from '@/components/CurrencySelect.vue'
  import DateField from '@/components/DateField.vue'
  import PlaceFields from '@/components/PlaceFields.vue'
  import SetImage from '@/components/SetImage.vue'
  import { useEuroPreview } from '@/composables/useDisplayCurrency'
  import { foreignEntryOn } from '@/composables/useDisplayPrefs'
  import { useFormMemory } from '@/composables/useFormMemory'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { type CurrencyCode, currencySymbol, toNumber } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{
    catalog: Pick<Catalog, 'catalog_num' | 'name' | 'image_url' | 'kind'> | null
    /** Kupuje sa z Chcem: nápoveda povie, že odtiaľ po uložení zmizne. */
    wishlistId?: number | null
  }>()
  /** `saved` nesie, či set ostal v Chcem (karta v Chcem ukáže „V zbierke“). */
  const emit = defineEmits<{ saved: [keptInWishlist: boolean] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()
  const collection = useCollectionStore()
  const memory = useFormMemory()

  const quantity = ref(1)
  const condition = ref<ItemCondition>('new_sealed')
  const price = ref('')
  /** Mena kúpy (Kúpu a predaj zadávať aj v inej mene); eurá prepočíta server. */
  const currency = ref<CurrencyCode>('EUR')
  const purchaseDate = ref('')
  const showCurrency = computed(() => foreignEntryOn() || currency.value !== 'EUR')
  const pricePreview = useEuroPreview(price, currency, purchaseDate)
  const place = ref<string | null>('')
  const location = ref<string | null>('')
  const box = ref<string | null>('')
  const saving = ref(false)
  const error = ref<string | null>(null)

  const isFigure = computed(() => props.catalog?.kind === 'minifig')
  const conditionItems = computed(() => CONDITIONS.map(value => ({ value, title: t(`condition.${value}`) })))

  watch(open, async isOpen => {
    if (!isOpen) return
    await memory.load()
    // Stav, dátum a miesta podľa Nastavení → Formuláre, inak predvolené.
    const start = memory.initial()
    quantity.value = 1
    condition.value = start.condition
    price.value = ''
    purchaseDate.value = start.date
    place.value = start.place
    location.value = start.location
    box.value = start.box
    error.value = null
    if (collection.locations.length === 0) collection.loadLocations()
  })

  /**
   * Uloží kúpu. Pri kúpe z Chcem rozhodne tlačidlo: `keepWishlist` nechá set
   * v Chcem (napríklad keď chcem ďalší kus), inak ho server vyradí.
   */
  async function save (keepWishlist = false): Promise<void> {
    if (!props.catalog || quantity.value < 1) return
    saving.value = true
    error.value = null
    const unit = toNumber(price.value)
    const { error: err } = await api.POST('/items', {
      body: {
        catalog_num: props.catalog.catalog_num,
        quantity: quantity.value,
        condition: condition.value,
        unidentified: false,
        // Figúrka v zatvorenom sáčku sa cení ako sáčok, rozbalená ako komplet.
        price_variant: isFigure.value ? (condition.value === 'new_sealed' ? 'sealed' : 'complete') : null,
        // Nový set v krabici má spravidla krabicu aj návod, figúrka nič z toho.
        flags: isFigure.value || condition.value !== 'new_sealed' ? [] : ['has_box', 'has_manual'],
        ...(currency.value === 'EUR'
          ? { purchase_price_eur: unit === null ? null : String(unit) }
          : { purchase_currency: currency.value, purchase_price_original: unit === null ? null : String(unit) }),
        purchase_date: purchaseDate.value || null,
        purchase_place: (place.value ?? '').trim() || null,
        location: (location.value ?? '').trim() || null,
        box: (box.value ?? '').trim() || null,
        keep_wishlist: keepWishlist,
      },
    })
    if (err) {
      saving.value = false
      error.value = errorMessage(err, t('purchase.failed'))
      return
    }
    memory.remember({
      condition: condition.value,
      date: purchaseDate.value,
      place: place.value ?? '',
      location: location.value ?? '',
      box: box.value ?? '',
    })
    notify.success(t('notice.addedPieces', { name: props.catalog.name, count: quantity.value }))
    saving.value = false
    open.value = false
    collection.refreshAll()
    emit('saved', keepWishlist)
  }
</script>

<template>
  <v-dialog v-model="open" max-width="680">
    <v-card v-if="catalog">
      <v-card-item>
        <template #prepend>
          <SetImage
            :alt="catalog.name"
            class="me-3"
            rounded="md"
            :size="56"
            :src="imageSrc(catalog.image_url) ?? undefined"
            style="width: 56px"
          />
        </template>

        <v-card-title>{{ t('purchase.title') }}</v-card-title>
        <v-card-subtitle>{{ catalog.name }} · {{ catalog.catalog_num }}</v-card-subtitle>
      </v-card-item>

      <v-card-text class="d-flex flex-column ga-3">
        <v-alert v-if="error" density="comfortable" type="error" variant="tonal">{{ error }}</v-alert>

        <div class="d-flex ga-3">
          <v-text-field
            v-model.number="quantity"
            hide-details
            :label="t('add.quantity')"
            max="99"
            min="1"
            style="max-width: 120px"
            type="number"
          />

          <v-select
            v-model="condition"
            hide-details
            item-title="title"
            item-value="value"
            :items="conditionItems"
            :label="t('add.condition')"
          />
        </div>

        <div class="d-flex ga-3">
          <CurrencySelect v-if="showCurrency" v-model="currency" />

          <v-text-field
            v-model="price"
            :hint="pricePreview.text.value ?? t('add.perPiece')"
            :label="t('add.purchasePrice')"
            persistent-hint
            :prefix="currencySymbol(currency)"
            type="number"
          />

          <DateField v-model="purchaseDate" clearable :label="t('add.purchaseDate')" />
        </div>

        <v-combobox
          v-model="place"
          hide-details
          :items="collection.purchasePlaces"
          :label="t('add.purchasePlace')"
          prepend-inner-icon="mdi-storefront-outline"
        />

        <PlaceFields v-model:box="box" v-model:location="location" />

        <div class="text-body-small text-medium-emphasis">
          {{ wishlistId ? t('purchase.hintWishlist') : t('purchase.hint') }}
        </div>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.cancel') }}</v-btn>

        <template v-if="wishlistId">
          <v-btn
            :disabled="quantity < 1 || saving"
            prepend-icon="mdi-heart-outline"
            variant="tonal"
            @click="save(true)"
          >{{ t('wishlist.addAndKeep') }}</v-btn>

          <v-btn
            color="primary"
            :disabled="quantity < 1"
            :loading="saving"
            prepend-icon="mdi-check"
            variant="flat"
            @click="save(false)"
          >{{ t('wishlist.addAndRemove') }}</v-btn>
        </template>

        <v-btn
          v-else
          color="primary"
          :disabled="quantity < 1"
          :loading="saving"
          prepend-icon="mdi-check"
          variant="flat"
          @click="save(false)"
        >{{ t('purchase.save') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
