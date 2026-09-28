<script setup lang="ts">
  import type { ValuedItem } from '@/api/types'
  /**
   * Zápis predaja jedného kusu. Hneď ukáže, aký bude realizovaný zisk,
   * a to čistý: po odpočítaní poplatkov trhoviska a poštovného.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import DateField from '@/components/DateField.vue'
  import { useCollectionStore } from '@/stores/collection'
  import { isoDate, money, toNumber } from '@/utils/format'

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{ item: ValuedItem | null }>()
  const emit = defineEmits<{
    confirm: [payload: {
      sold_price_eur: string
      sold_date: string
      sold_via: string | null
      sold_fees_eur: string | null
      sold_shipping_eur: string | null
    }]
  }>()

  const { t } = useI18n()

  const price = ref('')
  const date = ref(isoDate())
  const channel = ref<string | null>('')
  const fees = ref('')
  const shipping = ref('')
  const saving = ref(false)

  const collection = useCollectionStore()

  watch(open, isOpen => {
    if (isOpen && collection.saleChannels.length === 0) collection.loadLocations()
    if (isOpen) {
      price.value = props.item ? String(toNumber(props.item.market_value) ?? '') : ''
      date.value = isoDate()
      channel.value = ''
      fees.value = ''
      shipping.value = ''
      saving.value = false
    }
  })

  const purchase = computed(() => toNumber(props.item?.purchase_price_eur) ?? 0)
  const costs = computed(() => (toNumber(fees.value) ?? 0) + (toNumber(shipping.value) ?? 0))
  const profit = computed(() => {
    const sale = toNumber(price.value)
    if (sale === null) return null
    return sale - costs.value - purchase.value
  })

  /** Prázdne pole je „nič“, nie nula; záporné náklady nedávajú zmysel. */
  function amount (raw: string): string | null {
    const value = toNumber(raw)
    return value !== null && value > 0 ? String(value) : null
  }

  const valid = computed(() => {
    const sale = toNumber(price.value)
    const badCost = [fees.value, shipping.value].some(v => (toNumber(v) ?? 0) < 0)
    return sale !== null && sale > 0 && Boolean(date.value) && !badCost
  })

  function close (): void {
    open.value = false
  }

  function confirm (): void {
    if (!valid.value) return
    saving.value = true
    emit('confirm', {
      sold_price_eur: String(toNumber(price.value)),
      sold_date: date.value,
      sold_via: (channel.value ?? '').trim() || null,
      sold_fees_eur: amount(fees.value),
      sold_shipping_eur: amount(shipping.value),
    })
  }
</script>

<template>
  <v-dialog v-model="open" max-width="460">
    <v-card>
      <v-card-title>{{ t('sell.title') }}</v-card-title>
      <v-card-subtitle v-if="item">{{ item.catalog.name }} · {{ item.catalog_num }}</v-card-subtitle>

      <v-card-text class="d-flex flex-column ga-3 pt-4">
        <v-text-field
          v-model="price"
          autofocus
          :label="t('sell.price')"
          prefix="€"
          type="number"
        />

        <DateField v-model="date" :label="t('sell.date')" />

        <v-combobox
          v-model="channel"
          :items="collection.saleChannels"
          :label="t('sell.channel')"
          :placeholder="t('sell.channels')"
        />

        <div class="d-flex ga-3">
          <v-text-field
            v-model="fees"
            :label="t('sell.fees')"
            min="0"
            prefix="€"
            type="number"
          />

          <v-text-field
            v-model="shipping"
            :label="t('sell.shipping')"
            min="0"
            prefix="€"
            type="number"
          />
        </div>

        <div class="text-caption text-medium-emphasis mt-n2">{{ t('sell.costsHint') }}</div>

        <v-alert
          v-if="profit !== null"
          :color="profit >= 0 ? 'positive' : 'negative'"
          density="comfortable"
          variant="tonal"
        >
          {{ profit >= 0
            ? t('sell.profitPreview', { value: money(profit, { sign: true }) })
            : t('sell.lossPreview', { value: money(profit) }) }}
        </v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="close">{{ t('common.cancel') }}</v-btn>

        <v-btn
          color="primary"
          :disabled="!valid"
          :loading="saving"
          variant="flat"
          @click="confirm"
        >{{ t('sell.confirm') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
