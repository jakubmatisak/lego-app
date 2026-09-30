<script setup lang="ts">
  /**
   * Nový odkaz na pozretie: zbierka alebo Chcem, a buď všetko, alebo len
   * vybrané sety (pri sérii celá séria). Zoznam na výber je zo servera:
   * karty Zbierky (zoskupené podľa setu) alebo položky Chcem.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import SetImage from '@/components/SetImage.vue'
  import { fold } from '@/utils/text'

  interface Choice { num: string, name: string, image: string | null, theme: string | null }

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{ kind: 'collection' | 'wishlist' }>()
  const emit = defineEmits<{ create: [catalogNums: string[] | null] }>()

  const { t } = useI18n()
  const mode = ref<'all' | 'chosen'>('all')
  const choices = ref<Choice[]>([])
  const picked = ref(new Set<string>())
  const search = ref<string | null>('')
  const loading = ref(false)

  const shown = computed(() => {
    const words = fold(search.value ?? '').split(/\s+/).filter(Boolean)
    return choices.value.filter(c => {
      const hay = fold(`${c.name} ${c.num} ${c.theme ?? ''}`)
      return words.every(w => hay.includes(w))
    })
  })

  async function load (): Promise<void> {
    loading.value = true
    if (props.kind === 'wishlist') {
      const { data } = await api.GET('/wishlist', {})
      choices.value = (data ?? []).map(w => ({
        num: w.catalog_num, name: w.catalog.name, image: w.catalog.image_url ?? null, theme: w.catalog.theme ?? null,
      }))
    } else {
      const { data } = await api.GET('/items/grouped', { params: { query: { by: 'series', sort: 'name' } as never } })
      choices.value = (data ?? []).map(r => ({
        num: r.catalog.catalog_num, name: r.catalog.name, image: r.catalog.image_url ?? null, theme: r.catalog.theme ?? null,
      }))
    }
    loading.value = false
  }

  function toggle (num: string): void {
    const next = new Set(picked.value)
    if (next.has(num)) next.delete(num)
    else next.add(num)
    picked.value = next
  }

  function pickShown (on: boolean): void {
    const next = new Set(picked.value)
    for (const c of shown.value) {
      if (on) next.add(c.num)
      else next.delete(c.num)
    }
    picked.value = next
  }

  const canCreate = computed(() => mode.value === 'all' || picked.value.size > 0)

  function create (): void {
    emit('create', mode.value === 'all' ? null : [...picked.value])
    open.value = false
  }

  watch(open, isOpen => {
    if (!isOpen) return
    mode.value = 'all'
    picked.value = new Set()
    search.value = ''
    load()
  })
</script>

<template>
  <v-dialog v-model="open" max-width="640" scrollable>
    <v-card :title="kind === 'wishlist' ? t('settings.shareKindWishlist') : t('settings.shareKindCollection')">
      <v-card-text class="d-flex flex-column ga-3">
        <v-btn-toggle
          v-model="mode"
          color="primary"
          density="comfortable"
          mandatory
          variant="outlined"
        >
          <v-btn value="all">{{ t('share.all') }}</v-btn>
          <v-btn value="chosen">{{ t('share.chosen') }}</v-btn>
        </v-btn-toggle>

        <div class="text-body-medium text-medium-emphasis">
          {{ mode === 'all' ? t('share.allHint') : t('share.chosenHint') }}
        </div>

        <template v-if="mode === 'chosen'">
          <div class="d-flex align-center ga-2 flex-wrap">
            <v-text-field
              v-model="search"
              clearable
              density="compact"
              hide-details
              :placeholder="t('share.search')"
              prepend-inner-icon="mdi-magnify"
              style="min-width: 220px"
              variant="outlined"
            />

            <v-btn size="small" variant="text" @click="pickShown(true)">{{ t('share.pickShown') }}</v-btn>
            <v-btn size="small" variant="text" @click="pickShown(false)">{{ t('share.unpickShown') }}</v-btn>
          </div>

          <v-progress-linear v-if="loading" color="primary" indeterminate />

          <v-list v-else class="share-list" density="compact">
            <v-list-item
              v-for="c in shown"
              :key="c.num"
              :active="picked.has(c.num)"
              @click="toggle(c.num)"
            >
              <template #prepend>
                <v-icon
                  class="me-2"
                  :color="picked.has(c.num) ? 'primary' : undefined"
                  :icon="picked.has(c.num) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
                />

                <SetImage
                  :alt="c.name"
                  class="me-3"
                  rounded="sm"
                  :size="36"
                  :src="c.image"
                />
              </template>

              <v-list-item-title>{{ c.name }}</v-list-item-title>
              <v-list-item-subtitle>{{ c.num }}<span v-if="c.theme"> · {{ c.theme }}</span></v-list-item-subtitle>
            </v-list-item>
          </v-list>

          <div class="text-body-small">
            {{ t('share.pickedCount', { sets: t('collection.setsPlural', picked.size, { named: { count: picked.size } }) }) }}
          </div>
        </template>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.cancel') }}</v-btn>
        <v-btn color="primary" :disabled="!canCreate" variant="flat" @click="create">{{ t('share.create') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
  .share-list {
    max-height: 360px;
    overflow-y: auto;
  }
</style>
