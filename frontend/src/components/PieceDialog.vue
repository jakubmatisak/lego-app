<script setup lang="ts">
  import type { ItemCondition, ValuedItem } from '@/api/types'
  /**
   * Úprava jedného kusu. Opraviť sa dá všetko, čo sa zadáva pri pridaní,
   * lebo pomýliť sa je ľahké a inak by nezostalo než kus zmazať a založiť
   * odznova, čím by sa stratila jeho história.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { CONDITIONS, FLAGS, PURPOSES, VARIANTS } from '@/api/types'
  import DateField from '@/components/DateField.vue'
  import PlaceFields from '@/components/PlaceFields.vue'
  import { useCollectionStore } from '@/stores/collection'
  import { toNumber } from '@/utils/format'
  import { priceChange } from '@/utils/priceEdit'

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{ item: ValuedItem | null, locations?: string[] }>()
  const emit = defineEmits<{
    save: [payload: Record<string, unknown>]
    remove: [id: number]
  }>()

  const { t } = useI18n()

  const condition = ref<ItemCondition>('new_sealed')
  const variant = ref<string | null>(null)
  const flags = ref<string[]>([])
  const purpose = ref<string | null>(null)
  const location = ref<string | null>('')
  const box = ref<string | null>('')
  const price = ref('')
  const date = ref('')
  const place = ref<string | null>('')
  const note = ref('')
  const saving = ref(false)
  const confirmRemove = ref(false)

  /** Varianty ceny dávajú zmysel len pri minifigúrke. */
  const isMinifig = computed(() => props.item?.catalog.kind === 'minifig')

  const collection = useCollectionStore()

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
    price.value = String(toNumber(item.purchase_price_eur) ?? '')
    date.value = item.purchase_date ?? ''
    place.value = item.purchase_place ?? ''
    note.value = item.note ?? ''
    saving.value = false
    confirmRemove.value = false
  })

  function close (): void {
    open.value = false
  }

  function save (): void {
    saving.value = true
    emit('save', {
      condition: condition.value,
      price_variant: isMinifig.value ? variant.value : null,
      flags: flags.value,
      purpose: purpose.value,
      location: (location.value ?? '').trim() || null,
      // Prázdna krabica sa zmaže (server z prázdneho reťazca urobí null).
      box: (box.value ?? '').trim(),
      // Len zmenená cena; inak by sa zrušilo označenie doplnenej ceny.
      ...priceChange(props.item?.purchase_price_eur, price.value),
      purchase_date: date.value || null,
      purchase_place: (place.value ?? '').trim() || null,
      note: note.value.trim() || null,
    })
  }

  function remove (): void {
    if (!props.item) return
    saving.value = true
    emit('remove', props.item.id)
  }
</script>

<template>
  <v-dialog v-model="open" max-width="680" scrollable>
    <v-card v-if="item">
      <v-card-title>{{ t('piece.title') }}</v-card-title>
      <v-card-subtitle>{{ item.catalog.name }} · {{ item.catalog_num }}</v-card-subtitle>

      <v-card-text class="d-flex flex-column ga-4 pt-4">
        <div>
          <div class="text-subtitle-2 mb-2">{{ t('piece.condition') }}</div>

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
          <div class="text-subtitle-2 mb-2">{{ t('piece.variant') }}</div>

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
          <div class="text-subtitle-2 mb-2">{{ t('piece.flags') }}</div>

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
          <div class="text-subtitle-2 mb-2">{{ t('purpose.label') }}</div>

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
          <v-text-field
            v-model="price"
            :hide-details="!item.purchase_price_auto"
            :hint="item.purchase_price_auto ? t('purchaseAuto.dialogHint') : undefined"
            :label="t('piece.price')"
            persistent-hint
            prefix="€"
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
        <v-btn variant="text" @click="close">{{ t('common.cancel') }}</v-btn>

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
