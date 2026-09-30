<script setup lang="ts">
  import type { CmfMember, CmfSeries, ItemCondition } from '@/api/types'
  /**
   * „Mám všetky“: celá séria naraz, zaplatená jednou sumou.
   *
   * Suma sa rozpočíta na figúrky na strane servera, na centy presne, takže
   * zisk každej figúrky sedí a súčet je presne to, čo sa zaplatilo. Bežne sa
   * pridajú len chýbajúce figúrky; keď bola kúpená celá sada navyše, dajú sa
   * pridať aj tie, ktoré už mám, ako duplikáty. Kúpené figúrky z Chcem
   * vyradí server (`POST /items/bulk`).
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import { CONDITIONS } from '@/api/types'
  import DateField from '@/components/DateField.vue'
  import PlaceFields from '@/components/PlaceFields.vue'
  import SetImage from '@/components/SetImage.vue'
  import { useFormMemory } from '@/composables/useFormMemory'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { exactMoney, toNumber } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{ series: CmfSeries, members: CmfMember[] }>()
  const emit = defineEmits<{ saved: [] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()
  const collection = useCollectionStore()
  const memory = useFormMemory()

  const includeOwned = ref(false)
  const total = ref('')
  const condition = ref<ItemCondition>('new_sealed')
  const purchaseDate = ref('')
  const place = ref<string | null>('')
  const location = ref<string | null>('')
  const box = ref<string | null>('')
  const saving = ref(false)
  const error = ref<string | null>(null)

  const missing = computed(() => props.members.filter(m => m.owned === 0))
  const targets = computed(() => (includeOwned.value ? props.members : missing.value))
  const perPiece = computed(() => {
    const value = toNumber(total.value)
    return value === null || targets.value.length === 0 ? null : value / targets.value.length
  })
  const conditionItems = computed(() => CONDITIONS.map(value => ({ value, title: t(`condition.${value}`) })))

  watch(open, async isOpen => {
    if (!isOpen) return
    await memory.load()
    const start = memory.initial()
    // Keď už nič nechýba, jediný zmysel je pridať celú sadu znova.
    includeOwned.value = missing.value.length === 0
    total.value = ''
    condition.value = start.condition
    purchaseDate.value = start.date
    place.value = start.place
    location.value = start.location
    box.value = start.box
    error.value = null
    if (collection.locations.length === 0) collection.loadLocations()
  })

  async function save (): Promise<void> {
    if (targets.value.length === 0) return
    saving.value = true
    error.value = null
    const value = toNumber(total.value)
    const { error: err } = await api.POST('/items/bulk', {
      body: {
        members: targets.value.map(m => ({ catalog_num: m.catalog.catalog_num, quantity: 1 })),
        condition: condition.value,
        // Figúrka v zatvorenom sáčku sa cení ako sáčok, rozbalená ako komplet.
        price_variant: condition.value === 'new_sealed' ? 'sealed' : 'complete',
        purchase_total_eur: value === null ? null : String(value),
        purchase_date: purchaseDate.value || null,
        purchase_place: (place.value ?? '').trim() || null,
        location: (location.value ?? '').trim() || null,
        box: (box.value ?? '').trim() || null,
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
    notify.success(t('notice.addedPieces', { name: props.series.name, count: targets.value.length }))
    saving.value = false
    open.value = false
    collection.refreshAll()
    emit('saved')
  }
</script>

<template>
  <v-dialog v-model="open" max-width="680">
    <v-card>
      <v-card-item>
        <template #prepend>
          <SetImage
            :alt="series.name"
            class="me-3"
            rounded="md"
            :size="56"
            :src="imageSrc(series.image_url) ?? undefined"
            style="width: 56px"
          />
        </template>

        <v-card-title>{{ t('purchase.wholeSeriesTitle') }}</v-card-title>
        <v-card-subtitle>{{ series.name }}</v-card-subtitle>
      </v-card-item>

      <v-card-text class="d-flex flex-column ga-3">
        <v-alert v-if="error" density="comfortable" type="error" variant="tonal">{{ error }}</v-alert>

        <v-switch
          v-if="missing.length > 0 && missing.length < members.length"
          v-model="includeOwned"
          color="primary"
          density="compact"
          hide-details
          :label="t('purchase.includeOwned')"
        />

        <div class="d-flex ga-3">
          <v-text-field
            v-model="total"
            autofocus
            :label="t('purchase.totalPrice')"
            prefix="€"
            type="number"
          />

          <v-select
            v-model="condition"
            item-title="title"
            item-value="value"
            :items="conditionItems"
            :label="t('add.condition')"
          />
        </div>

        <div class="d-flex ga-3">
          <DateField v-model="purchaseDate" clearable hide-details :label="t('add.purchaseDate')" />

          <v-combobox
            v-model="place"
            hide-details
            :items="collection.purchasePlaces"
            :label="t('add.purchasePlace')"
            prepend-inner-icon="mdi-storefront-outline"
          />
        </div>

        <PlaceFields v-model:box="box" v-model:location="location" />

        <v-card class="pa-3" color="surface-variant" flat>
          <div class="text-body-medium">
            {{ t('purchase.willAddPlural', targets.length, { named: { count: targets.length } }) }}
            <template v-if="perPiece !== null">
              · {{ t('purchase.perPieceAbout', { price: exactMoney(perPiece) }) }}
            </template>
          </div>

          <div class="text-body-small text-medium-emphasis mt-1">{{ t('purchase.splitHint') }}</div>
        </v-card>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.cancel') }}</v-btn>

        <v-btn
          color="primary"
          :disabled="targets.length === 0"
          :loading="saving"
          prepend-icon="mdi-check-all"
          variant="flat"
          @click="save"
        >{{ t('purchase.save') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
