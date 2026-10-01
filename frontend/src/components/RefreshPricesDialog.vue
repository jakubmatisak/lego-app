<script setup lang="ts">
  /**
   * Potvrdenie obnovy cien z hornej lišty. Používateľ vidí, koľko volaní
   * dnes minul, a vyberie, koľko cien sa má obnoviť; každá cena je jedno
   * volanie. Poradie určuje server: najprv ceny, ktoré chýbajú, potom tie
   * obnovené najdávnejšie (``services/refresh.py::collect_targets``).
   *
   * Čísla sú tie isté ako na karte limitov (``calls_used``/``calls_limit``
   * z ``/prices/refresh-status`` rátajú rovnako ako ``/usage``).
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { usePriceStore } from '@/stores/prices'

  /** Predvolený počet cien na jedno kliknutie. */
  const DEFAULT_COUNT = 50
  /** Koľko volaní denne dáva služba; appka si z nich nechá rezervu. */

  const open = defineModel<boolean>({ required: true })
  const emit = defineEmits<{ confirm: [count: number] }>()

  const { t } = useI18n()
  const prices = usePriceStore()

  const count = ref<string>(String(DEFAULT_COUNT))

  /** Zvyšok dnešného limitu appky; nikdy viac, než pustí počítadlo kľúča. */
  const left = computed(() =>
    Math.max(0, Math.min(prices.callsLeft, prices.callsLimit - prices.callsUsed)),
  )

  const parsed = computed(() => {
    const value = Number(count.value)
    return Number.isInteger(value) ? value : null
  })
  const valid = computed(() => parsed.value !== null && parsed.value >= 1 && parsed.value <= left.value)

  function prefill (): void {
    count.value = String(Math.max(1, Math.min(DEFAULT_COUNT, left.value)))
  }

  watch(open, async isOpen => {
    if (!isOpen) return
    prefill()
    // Čerstvé čísla: medzitým mohla minúť volania obnova z detailu či Overiť cenu.
    await prices.fetchStatus()
    prefill()
  }, { immediate: true })

  function confirm (): void {
    if (!valid.value || parsed.value === null) return
    emit('confirm', parsed.value)
    open.value = false
  }
</script>

<template>
  <v-dialog v-model="open" max-width="440">
    <v-card>
      <v-card-title>{{ t('prices.dialog.title') }}</v-card-title>

      <v-card-text class="d-flex flex-column ga-3 pt-4">
        <v-text-field
          v-model="count"
          autofocus
          data-test="refresh-count"
          :error-messages="valid ? [] : [t('prices.dialog.range', { max: left })]"
          :hint="t('prices.dialog.order')"
          :label="t('prices.dialog.count')"
          :max="left"
          min="1"
          persistent-hint
          type="number"
          @keydown.enter="confirm"
        />

        <div class="text-body-medium" data-test="refresh-usage">
          {{ t('prices.dialog.usage', { used: prices.callsUsed, limit: prices.callsLimit, left }) }}
        </div>

      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.cancel') }}</v-btn>

        <v-btn
          color="primary"
          data-test="refresh-confirm"
          :disabled="!valid"
          variant="flat"
          @click="confirm"
        >{{ t('prices.dialog.confirm') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
