<script setup lang="ts">
  import type { Category, CategoryRule } from '@/api/types'
  /**
   * Správa vlastných kategórií: názov, farba a pravidlá.
   *
   * Ručné zaradenie a vylúčenie sa robí v detaile setu, tu sa len ukazuje,
   * koľko ich kategória má. Pravidlo stačí jedno, aby set do nej patril.
   */
  import { computed, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import { useFilterStore } from '@/stores/filters'
  import { useNotifyStore } from '@/stores/notify'

  const open = defineModel<boolean>({ required: true })
  const emit = defineEmits<{ changed: [] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()
  const store = useFilterStore()

  const COLORS = ['red', 'orange', 'amber', 'green', 'teal', 'blue', 'indigo', 'purple', 'pink', 'brown', 'blue-grey']
  const FIELDS: CategoryRule['field'][] = ['name', 'theme', 'subtheme']
  const OPS: CategoryRule['op'][] = ['word', 'contains', 'equals']

  /** Upravovaná kategória. ``null`` id znamená novú. */
  const editing = ref<{ id: number | null, name: string, color: string | null, rules: CategoryRule[] } | null>(null)
  const confirmRemove = ref(false)
  const saving = ref(false)
  const error = ref<string | null>(null)

  const fieldItems = computed(() => FIELDS.map(value => ({ value, title: t(`categories.field.${value}`) })))
  const opItems = computed(() => OPS.map(value => ({ value, title: t(`categories.op.${value}`) })))

  function ruleText (rule: CategoryRule): string {
    return `${t(`categories.field.${rule.field}`)} ${t(`categories.op.${rule.op}`)} „${rule.value}“`
  }

  function startNew (): void {
    editing.value = { id: null, name: '', color: 'blue', rules: [] }
    confirmRemove.value = false
    error.value = null
  }

  function startEdit (category: Category): void {
    editing.value = {
      id: category.id,
      name: category.name,
      color: category.color,
      rules: category.rules.map(r => ({ ...r })),
    }
    confirmRemove.value = false
    error.value = null
  }

  function addRule (): void {
    editing.value?.rules.push({ field: 'name', op: 'word', value: '' })
  }

  async function save (): Promise<void> {
    if (!editing.value || !editing.value.name.trim()) return
    saving.value = true
    error.value = null
    const body = {
      name: editing.value.name.trim(),
      color: editing.value.color,
      // Prázdne pravidlo by nesedelo na nič, nemá zmysel ho ukladať.
      rules: editing.value.rules.filter(r => r.value.trim()).map(r => ({ ...r, value: r.value.trim() })),
    }
    const result = editing.value.id === null
      ? await api.POST('/categories', { body })
      : await api.PATCH('/categories/{category_id}', {
        params: { path: { category_id: editing.value.id } },
        body,
      })
    saving.value = false
    if (result.error) {
      error.value = errorMessage(result.error, 'Kategóriu sa nepodarilo uložiť')
      return
    }
    store.categories = result.data ?? []
    notify.success(t('notice.categorySaved', { name: body.name }))
    editing.value = null
    emit('changed')
  }

  async function remove (): Promise<void> {
    if (!editing.value?.id) return
    const { data, error: err } = await api.DELETE('/categories/{category_id}', {
      params: { path: { category_id: editing.value.id } },
    })
    if (err) {
      notify.error(err, t('notice.deleteFailed'))
      return
    }
    store.categories = data ?? []
    notify.success(t('notice.categoryDeleted'))
    // Zmazanú kategóriu treba vyhodiť aj z aktívneho filtra.
    store.filters.category = store.filters.category.filter(id => id !== editing.value?.id)
    editing.value = null
    emit('changed')
  }

  watch(open, isOpen => {
    if (isOpen) {
      editing.value = null
      store.loadCategories()
    }
  })
</script>

<template>
  <v-dialog v-model="open" max-width="640" scrollable>
    <v-card>
      <v-card-title>{{ editing ? (editing.id === null ? t('categories.new') : editing.name || t('categories.edit')) : t('categories.title') }}</v-card-title>

      <v-card-text class="pt-2">
        <v-alert
          v-if="error"
          class="mb-3"
          density="comfortable"
          type="error"
          variant="tonal"
        >{{ error }}</v-alert>

        <!-- Zoznam kategórií -->
        <template v-if="!editing">
          <div v-if="store.categories.length === 0" class="text-body-medium text-medium-emphasis">
            {{ t('categories.empty') }}
          </div>

          <v-list v-else density="comfortable" lines="two">
            <v-list-item v-for="category in store.categories" :key="category.id" @click="startEdit(category)">
              <template #prepend>
                <span class="cat-dot me-3" :class="`bg-${category.color ?? 'grey'}`" />
              </template>

              <v-list-item-title class="font-weight-medium">{{ category.name }}</v-list-item-title>

              <v-list-item-subtitle>
                {{ t('categories.setsPlural', category.sets, { named: { count: category.sets } }) }}
                <span v-if="category.manual_in"> · {{ t('categories.manualIn', { count: category.manual_in }) }}</span>
                <span v-if="category.manual_out"> · {{ t('categories.manualOut', { count: category.manual_out }) }}</span>
                <div v-for="(rule, i) in category.rules" :key="i" class="text-body-small">{{ ruleText(rule) }}</div>
              </v-list-item-subtitle>

              <template #append>
                <v-icon icon="mdi-chevron-right" />
              </template>
            </v-list-item>
          </v-list>
        </template>

        <!-- Úprava jednej kategórie -->
        <div v-else class="d-flex flex-column ga-4">
          <v-text-field v-model="editing.name" autofocus hide-details :label="t('categories.name')" />

          <div>
            <div class="text-title-small mb-2">{{ t('categories.color') }}</div>

            <div class="d-flex flex-wrap ga-2">
              <button
                v-for="color in COLORS"
                :key="color"
                :aria-label="color"
                class="cat-swatch"
                :class="[`bg-${color}`, { 'cat-swatch--on': editing.color === color }]"
                type="button"
                @click="editing.color = color"
              />
            </div>
          </div>

          <div>
            <div class="text-title-small mb-1">{{ t('categories.rules') }}</div>
            <div class="text-body-small text-medium-emphasis mb-2">{{ t('categories.rulesHint') }}</div>

            <div v-if="editing.rules.length === 0" class="text-body-medium text-medium-emphasis mb-2">
              {{ t('categories.noRules') }}
            </div>

            <div
              v-for="(rule, i) in editing.rules"
              :key="i"
              class="d-flex ga-2 align-center flex-wrap mb-2"
            >
              <v-select
                v-model="rule.field"
                density="compact"
                hide-details
                :items="fieldItems"
                style="max-width: 140px"
                variant="outlined"
              />

              <v-select
                v-model="rule.op"
                density="compact"
                hide-details
                :items="opItems"
                style="max-width: 180px"
                variant="outlined"
              />

              <v-text-field
                v-model="rule.value"
                density="compact"
                hide-details
                :label="t('categories.value')"
                style="min-width: 120px"
                variant="outlined"
              />

              <v-btn
                icon="mdi-close"
                size="small"
                :title="t('common.cancel')"
                variant="text"
                @click="editing.rules.splice(i, 1)"
              />
            </div>

            <v-btn prepend-icon="mdi-plus" size="small" variant="text" @click="addRule">
              {{ t('categories.addRule') }}
            </v-btn>
          </div>

          <v-alert v-if="confirmRemove" density="comfortable" type="warning" variant="tonal">
            {{ t('categories.removeHint') }}
          </v-alert>
        </div>
      </v-card-text>

      <v-card-actions>
        <template v-if="!editing">
          <v-btn color="primary" prepend-icon="mdi-plus" variant="flat" @click="startNew">
            {{ t('categories.new') }}
          </v-btn>

          <v-spacer />
          <v-btn variant="text" @click="open = false">{{ t('common.close') }}</v-btn>
        </template>

        <template v-else>
          <template v-if="editing.id !== null">
            <v-btn
              v-if="!confirmRemove"
              color="negative"
              prepend-icon="mdi-delete-outline"
              variant="text"
              @click="confirmRemove = true"
            >{{ t('categories.remove') }}</v-btn>

            <v-btn
              v-else
              color="negative"
              prepend-icon="mdi-delete"
              variant="flat"
              @click="remove"
            >{{ t('categories.removeConfirm') }}</v-btn>
          </template>

          <v-spacer />
          <v-btn variant="text" @click="editing = null">{{ t('common.back') }}</v-btn>

          <v-btn
            color="primary"
            :disabled="!editing.name.trim() || confirmRemove"
            :loading="saving"
            variant="flat"
            @click="save"
          >{{ t('categories.save') }}</v-btn>
        </template>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.cat-dot {
  border-radius: 50%;
  display: inline-block;
  height: 12px;
  width: 12px;
}

.cat-swatch {
  border: 2px solid transparent;
  border-radius: 50%;
  cursor: pointer;
  height: 28px;
  width: 28px;
}

.cat-swatch--on {
  box-shadow: 0 0 0 2px rgb(var(--v-theme-on-surface));
}
</style>
