<script setup lang="ts">
  /**
   * Lupa v rohu fotky setu (karta v Zbierke, detail setu). Otvorí fotku
   * veľkú a za ňou ďalšie fotky z Brickset. Galéria sa pýta až po kliknutí;
   * server ju má z databázy a z Brickset ju stiahne najviac raz na set.
   * Klik neotvorí detail setu, aj keď je lupa na karte, ktorá je odkazom.
   */
  import type { ViewerImage } from '@/components/ImageViewer.vue'
  import { ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { api } from '@/api/client'
  import ImageViewer from '@/components/ImageViewer.vue'

  const props = defineProps<{ num: string, name: string, imageUrl: string }>()

  const { t } = useI18n()
  const open = ref(false)
  const index = ref(0)
  const loading = ref(false)
  const images = ref<ViewerImage[]>([])
  let loaded = false

  async function zoom (): Promise<void> {
    if (!loaded) {
      loading.value = true
      const gallery: ViewerImage[] = []
      try {
        const { data } = await api.GET('/catalog/{num}/images', { params: { path: { num: props.num } } })
        if (data?.enabled) {
          for (const image of data.images ?? []) {
            gallery.push({ url: image.image_url, credit: t('detail.galleryCredit') })
          }
        }
        loaded = true
      } catch {
        // Bez galérie aspoň hlavná fotka; nabudúce sa skúsi znova.
      } finally {
        loading.value = false
      }
      images.value = [{ url: props.imageUrl }, ...gallery]
    }
    index.value = 0
    open.value = true
  }
</script>

<template>
  <v-btn
    :aria-label="t('detail.galleryOpen')"
    class="photo-zoom"
    density="comfortable"
    icon="mdi-magnify-plus-outline"
    :loading="loading"
    size="small"
    :title="t('detail.galleryOpen')"
    variant="tonal"
    @click.stop.prevent="zoom"
  />

  <ImageViewer v-model:index="index" v-model:open="open" :images="images" :name="name" />
</template>

<style scoped>
  .photo-zoom {
    position: absolute;
    right: 8px;
    bottom: 8px;
    background: rgb(var(--v-theme-surface));
    cursor: zoom-in;
  }
</style>
