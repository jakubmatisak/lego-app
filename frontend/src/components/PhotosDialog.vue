<script setup lang="ts">
  import type { Photo, ValuedItem } from '@/api/types'
  /**
   * Vlastné fotky kusu. Dôkaz stavu pre poistku a podklad k inzerátu.
   *
   * Obrázky sa sťahujú s prihlásením, preto nejdú rovno do <img src>:
   * načítajú sa ako blob a zobrazia cez dočasnú adresu, ktorá sa pri
   * zatvorení dialógu uvoľní.
   */
  import { onBeforeUnmount, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api, errorMessage } from '@/api/client'
  import { useNotifyStore } from '@/stores/notify'

  const open = defineModel<boolean>({ required: true })
  const props = defineProps<{ item: ValuedItem | null }>()
  const emit = defineEmits<{ changed: [itemId: number, count: number] }>()

  const { t } = useI18n()
  const notify = useNotifyStore()

  const photos = ref<Photo[]>([])
  const urls = ref<Record<number, string>>({})
  const uploading = ref(false)
  const error = ref<string | null>(null)
  const zoomed = ref<number | null>(null)
  const input = ref<HTMLInputElement | null>(null)

  function release (): void {
    for (const url of Object.values(urls.value)) URL.revokeObjectURL(url)
    urls.value = {}
  }

  async function loadImage (photo: Photo): Promise<void> {
    const { data } = await api.GET('/photos/{photo_id}', {
      params: { path: { photo_id: photo.id } },
      parseAs: 'blob',
    })
    if (data) urls.value[photo.id] = URL.createObjectURL(data as Blob)
  }

  async function load (): Promise<void> {
    if (!props.item) return
    const { data } = await api.GET('/items/{item_id}/photos', {
      params: { path: { item_id: props.item.id } },
    })
    photos.value = data ?? []
    await Promise.all(photos.value.map(p => loadImage(p)))
    emit('changed', props.item.id, photos.value.length)
  }

  async function upload (event: Event): Promise<void> {
    const files = [...((event.target as HTMLInputElement).files ?? [])]
    if (!props.item || files.length === 0) return
    uploading.value = true
    error.value = null
    let failed = false
    for (const file of files) {
      const body = new FormData()
      body.append('file', file)
      const { error: err } = await api.POST('/items/{item_id}/photos', {
        params: { path: { item_id: props.item.id } },
        body: body as never,
      })
      if (err) {
        error.value = errorMessage(err, t('photos.uploadFailed'))
        failed = true
        break
      }
    }
    if (!failed) notify.success(t('notice.photosAdded'))
    if (input.value) input.value.value = ''
    uploading.value = false
    release()
    await load()
  }

  async function remove (photo: Photo): Promise<void> {
    const { error: err } = await api.DELETE('/photos/{photo_id}', { params: { path: { photo_id: photo.id } } })
    if (err) {
      notify.error(err, t('notice.deleteFailed'))
      return
    }
    notify.success(t('notice.photoDeleted'))
    zoomed.value = null
    release()
    await load()
  }

  watch(open, isOpen => {
    error.value = null
    zoomed.value = null
    if (isOpen) {
      load()
    } else {
      release()
      photos.value = []
    }
  })

  onBeforeUnmount(release)
</script>

<template>
  <v-dialog v-model="open" max-width="720" scrollable>
    <v-card v-if="item">
      <v-card-title>{{ t('photos.title') }}</v-card-title>
      <v-card-subtitle>{{ item.catalog.name }} · {{ item.catalog_num }}</v-card-subtitle>

      <v-card-text class="d-flex flex-column ga-3 pt-4">
        <v-alert v-if="error" density="comfortable" type="error" variant="tonal">{{ error }}</v-alert>

        <div v-if="zoomed !== null && urls[zoomed]" class="d-flex flex-column ga-2">
          <img :alt="item.catalog.name" class="photo-zoom" :src="urls[zoomed]">

          <div class="d-flex ga-2">
            <v-btn prepend-icon="mdi-arrow-left" variant="text" @click="zoomed = null">
              {{ t('common.back') }}
            </v-btn>

            <v-spacer />

            <v-btn
              color="negative"
              prepend-icon="mdi-delete-outline"
              variant="text"
              @click="remove(photos.find(p => p.id === zoomed)!)"
            >{{ t('photos.remove') }}</v-btn>
          </div>
        </div>

        <template v-else>
          <div v-if="photos.length === 0" class="text-body-medium text-medium-emphasis">
            {{ t('photos.empty') }}
          </div>

          <div v-else class="photo-grid">
            <button
              v-for="photo in photos"
              :key="photo.id"
              class="photo-thumb"
              type="button"
              @click="zoomed = photo.id"
            >
              <img v-if="urls[photo.id]" :alt="item.catalog.name" :src="urls[photo.id]">
            </button>
          </div>
        </template>
      </v-card-text>

      <v-card-actions>
        <!--
          Bez atribútu capture: telefón ponúkne fotoaparát aj galériu.
          S ním by sa dalo len fotiť a hotové fotky by nešli vybrať.
        -->
        <input
          ref="input"
          accept="image/jpeg,image/png,image/webp"
          class="d-none"
          multiple
          type="file"
          @change="upload"
        >

        <v-btn
          color="primary"
          :loading="uploading"
          prepend-icon="mdi-camera-plus-outline"
          variant="flat"
          @click="input?.click()"
        >{{ t('photos.add') }}</v-btn>

        <span class="text-body-small text-medium-emphasis ms-2">{{ t('photos.hint') }}</span>

        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.close') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.photo-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(auto-fill, minmax(min(140px, 100%), 1fr));
}

.photo-thumb {
  aspect-ratio: 1;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 8px;
  cursor: zoom-in;
  overflow: hidden;
  padding: 0;
  background: rgb(var(--v-theme-surface-variant));
}

.photo-thumb img {
  height: 100%;
  object-fit: cover;
  width: 100%;
}

.photo-zoom {
  border-radius: 8px;
  max-height: 70vh;
  max-width: 100%;
  object-fit: contain;
}
</style>
