<script setup lang="ts">
  import type { CatalogCategory } from '@/api/types'
  /**
   * Kategórie jedného setu v detaile. Zaškrtnutie hovorí len „chcem ho tam“;
   * či na to treba ručné zaradenie, alebo vylúčenie proti pravidlu, rozhodne
   * server. Pri sérii sa kategória prenesie na všetky jej figúrky.
   */
  import { computed, onMounted, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import { useNotifyStore } from '@/stores/notify'

  const props = defineProps<{ num: string }>()
  const emit = defineEmits<{ manage: [] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()
  const rows = ref<CatalogCategory[]>([])
  const busy = ref<number | null>(null)

  const members = computed(() => rows.value.filter(r => r.member))

  async function load (): Promise<void> {
    const { data } = await api.GET('/catalog/{num}/categories', { params: { path: { num: props.num } } })
    rows.value = data ?? []
  }

  async function toggle (row: CatalogCategory): Promise<void> {
    busy.value = row.id
    const { data, error: err } = await api.PUT('/categories/{category_id}/members/{num}', {
      params: { path: { category_id: row.id, num: props.num } },
      body: { member: !row.member },
    })
    busy.value = null
    if (err || !data) {
      notify.error(err, t('notice.saveFailed'))
      return
    }
    rows.value = data
    notify.success(t('notice.membershipSaved'))
  }

  watch(() => props.num, load)
  onMounted(load)

  defineExpose({ reload: load })
</script>

<template>
  <div class="d-flex flex-wrap ga-1 align-center">
    <v-chip
      v-for="row in members"
      :key="row.id"
      label
      size="small"
      :title="row.reason === 'rule' ? t('categories.viaRule') : t('categories.viaManual')"
      variant="outlined"
    >
      <span class="cm-dot me-1" :class="`bg-${row.color ?? 'grey'}`" />
      {{ row.name }}
      <v-icon v-if="row.reason === 'rule'" class="ms-1" icon="mdi-auto-fix" size="x-small" />
    </v-chip>

    <v-menu :close-on-content-click="false" location="bottom start">
      <template #activator="{ props: menuProps }">
        <v-btn
          prepend-icon="mdi-tag-multiple-outline"
          size="small"
          variant="text"
          v-bind="menuProps"
        >{{ members.length === 0 ? t('categories.editMembership') : t('categories.inDetail') }}</v-btn>
      </template>

      <v-card min-width="260">
        <v-list v-if="rows.length > 0" density="compact">
          <v-list-item
            v-for="row in rows"
            :key="row.id"
            :disabled="busy === row.id"
            @click="toggle(row)"
          >
            <template #prepend>
              <v-checkbox-btn density="compact" :model-value="row.member" tabindex="-1" />
            </template>

            <v-list-item-title>
              <span class="cm-dot me-2" :class="`bg-${row.color ?? 'grey'}`" />{{ row.name }}
            </v-list-item-title>

            <v-list-item-subtitle v-if="row.member">
              {{ row.reason === 'rule' ? t('categories.viaRule') : t('categories.viaManual') }}
            </v-list-item-subtitle>
          </v-list-item>
        </v-list>

        <div v-else class="pa-3 text-body-2 text-medium-emphasis">{{ t('categories.empty') }}</div>

        <v-divider />

        <v-card-actions>
          <v-btn prepend-icon="mdi-cog-outline" size="small" variant="text" @click="emit('manage')">
            {{ t('filters.manage') }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-menu>
  </div>
</template>

<style scoped>
.cm-dot {
  border-radius: 50%;
  display: inline-block;
  height: 8px;
  width: 8px;
}
</style>
