<script setup lang="ts">
  /**
   * Čítačka čiarových kódov cez kameru.
   *
   * Prehliadač, ktorý vie čítať kódy sám (Chrome na Androide, Safari na
   * Macu), to robí sám. Inde (Chrome na Windows, Firefox, iPhone) nastúpi
   * ZXing vo WebAssembly. Jeho súbor je súčasťou appky, nič sa neťahá
   * z cudzieho servera.
   *
   * Kamera sa dá vybrať (notebook má často prednú, infračervenú aj
   * virtuálnu) a výber si pamätá prehliadač. Živý obraz ide len na https
   * alebo localhost.
   *
   * „Odfotiť kód“: keď beží živý obraz, urobí snímku z tej istej kamery
   * v najvyššom rozlíšení, aké kamera dá. Počítač totiž pri súbore ignoruje
   * „odfoť“ a otvoril by len výber súboru. Bez živého obrazu (telefón cez
   * http) otvorí fotoaparát telefónu. Obrázok z disku je zvlášť tlačidlo.
   *
   * Webkamera pruhy často nezaostrí, preto sa popri celom zábere skúša aj
   * zväčšený stred v odtieňoch šedej so zvýšeným kontrastom.
   */
  import { computed, onBeforeUnmount, ref, watch } from 'vue'
  import { useI18n } from 'vue-i18n'

  const open = defineModel<boolean>({ required: true })
  const emit = defineEmits<{ detected: [code: string] }>()

  const { t } = useI18n()

  const FORMATS = ['ean_13', 'ean_8', 'upc_a', 'upc_e'] as const
  const STORAGE_KEY = 'moje-kocky.camera'

  const video = ref<HTMLVideoElement | null>(null)
  const photoInput = ref<HTMLInputElement | null>(null)
  const error = ref<string | null>(null)
  const photoError = ref<string | null>(null)
  const starting = ref(false)
  const readingPhoto = ref(false)
  /** Beží živý obraz? Podľa toho „Odfotiť kód“ sníma z neho, alebo otvorí fotoaparát. */
  const live = ref(false)
  let tick = 0
  const cameras = ref<{ value: string, title: string }[]>([])
  const cameraId = ref<string | null>(loadCamera())
  let stream: MediaStream | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  const liveSupported = computed(() => window.isSecureContext && !!navigator.mediaDevices?.getUserMedia)

  type Source = HTMLVideoElement | ImageBitmap | HTMLCanvasElement
  interface Detector {
    detect: (source: Source) => Promise<{ rawValue: string }[]>
  }

  interface NativeDetector {
    getSupportedFormats?: () => Promise<string[]>
    new (options: object): Detector
  }

  function loadCamera (): string | null {
    try {
      return localStorage.getItem(STORAGE_KEY)
    } catch {
      return null
    }
  }

  function saveCamera (id: string | null): void {
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id)
    } catch {
      // Súkromné okno: výber kamery si len nezapamätáme.
    }
  }

  let detectorPromise: Promise<Detector> | null = null

  /** Čítačka sa pripraví raz, prepnutie kamery ju znova nenačítava. */
  function getDetector (): Promise<Detector> {
    detectorPromise ??= createDetector()
    return detectorPromise
  }

  /** Vlastná čítačka prehliadača, ak vie EAN; inak ZXing zo súborov appky. */
  async function createDetector (): Promise<Detector> {
    const Native = (globalThis as { BarcodeDetector?: NativeDetector }).BarcodeDetector
    if (Native?.getSupportedFormats) {
      const supported = await Native.getSupportedFormats()
      if (supported.includes('ean_13')) return new Native({ formats: [...FORMATS] })
    }
    const [{ BarcodeDetector, prepareZXingModule }, { default: wasmUrl }] = await Promise.all([
      import('barcode-detector/ponyfill'),
      import('zxing-wasm/reader/zxing_reader.wasm?url'),
    ])
    prepareZXingModule({
      overrides: {
        locateFile: (path: string, prefix: string) => (path.endsWith('.wasm') ? wasmUrl : prefix + path),
      },
    })
    return new BarcodeDetector({ formats: [...FORMATS] })
  }

  /**
   * Prvý rozumný kód. Keď ich je v zábere viac (aj falošný z tieňa), má
   * prednosť ten s predponou 5702, pod ktorou LEGO registruje svoje kódy.
   */
  function pickCode (codes: { rawValue: string }[]): string | null {
    const valid = codes.map(c => c.rawValue).filter(v => /^\d{8,13}$/.test(v))
    return valid.find(v => v.startsWith('5702')) ?? valid[0] ?? null
  }

  /**
   * Vyrovnanie tieňa: obraz sa vydelí svojou silno rozmazanou kópiou, takže
   * zostanú len pruhy a nie svetlo dopadajúce na krabicu. Skúšané na
   * skutočnej fotke: bez tohto ju ZXing neprečítal v žiadnom nastavení,
   * s ním áno. Pracuje sa na zmenšenom obraze, pre čítanie to stačí a je
   * to rýchle aj päťkrát za sekundu.
   */
  function flattened (source: HTMLVideoElement | ImageBitmap, maxWidth = 1000): HTMLCanvasElement | null {
    const srcW = source instanceof HTMLVideoElement ? source.videoWidth : source.width
    const srcH = source instanceof HTMLVideoElement ? source.videoHeight : source.height
    if (!srcW || !srcH) return null
    const scale = Math.min(1, maxWidth / srcW)
    const w = Math.round(srcW * scale)
    const h = Math.round(srcH * scale)

    const sharp = document.createElement('canvas')
    sharp.width = w
    sharp.height = h
    const sharpCtx = sharp.getContext('2d', { willReadFrequently: true })
    const blurred = document.createElement('canvas')
    blurred.width = w
    blurred.height = h
    const blurCtx = blurred.getContext('2d', { willReadFrequently: true })
    if (!sharpCtx || !blurCtx) return null

    sharpCtx.filter = 'grayscale(1)'
    sharpCtx.drawImage(source, 0, 0, w, h)
    // Rozmazanie asi na 3 % šírky: zmaže pruhy, tieň a odlesk ostanú.
    blurCtx.filter = `blur(${Math.max(8, Math.round(w * 0.027))}px)`
    blurCtx.drawImage(sharp, 0, 0)

    const image = sharpCtx.getImageData(0, 0, w, h)
    const background = blurCtx.getImageData(0, 0, w, h).data
    const pixels = image.data
    for (let i = 0; i < pixels.length; i += 4) {
      const value = Math.min(255, (pixels[i]! / (background[i]! + 1)) * 200)
      pixels[i] = value
      pixels[i + 1] = value
      pixels[i + 2] = value
    }
    sharpCtx.putImageData(image, 0, 0)
    return sharp
  }

  function finish (code: string): void {
    navigator.vibrate?.(80)
    stop()
    open.value = false
    emit('detected', code)
  }

  function stop (): void {
    if (timer !== null) clearTimeout(timer)
    timer = null
    for (const track of stream?.getTracks() ?? []) track.stop()
    stream = null
    live.value = false
  }

  /**
   * Stred záberu dvakrát zväčšený, šedý a kontrastnejší. Malý alebo mierne
   * rozmazaný kód z webkamery sa tak číta oveľa ochotnejšie.
   */
  function enhancedCenter (source: HTMLVideoElement | ImageBitmap): HTMLCanvasElement | null {
    const width = source instanceof HTMLVideoElement ? source.videoWidth : source.width
    const height = source instanceof HTMLVideoElement ? source.videoHeight : source.height
    if (!width || !height) return null
    const cropW = width * 0.7
    const cropH = height * 0.5
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(cropW * 2)
    canvas.height = Math.round(cropH * 2)
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.filter = 'grayscale(1) contrast(1.6)'
    ctx.drawImage(source, (width - cropW) / 2, (height - cropH) / 2, cropW, cropH, 0, 0, canvas.width, canvas.height)
    return canvas
  }

  /** Celý záber, a keď nič, zväčšený stred. */
  async function readStill (source: ImageBitmap): Promise<string | null> {
    const detector = await getDetector()
    // Od najlacnejšieho: celý záber, zväčšený stred, vyrovnaný tieň.
    const attempts: (() => HTMLCanvasElement | ImageBitmap | null)[] = [
      () => source,
      () => enhancedCenter(source),
      () => flattened(source),
      () => flattened(source, 1600),
    ]
    for (const attempt of attempts) {
      const image = attempt()
      if (!image) continue
      const code = pickCode(await detector.detect(image))
      if (code) return code
    }
    return null
  }

  /**
   * Snímka z bežiacej kamery. ImageCapture (Chrome) vezme fotku v plnom
   * rozlíšení snímača; kde nie je, poslúži aktuálny obrázok z videa.
   */
  async function grabFrame (): Promise<ImageBitmap | null> {
    const track = stream?.getVideoTracks()[0]
    const Capture = (globalThis as { ImageCapture?: new (t: MediaStreamTrack) => { takePhoto: () => Promise<Blob> } }).ImageCapture
    if (track && Capture) {
      try {
        return await createImageBitmap(await new Capture(track).takePhoto())
      } catch {
        // Niektoré webkamery fotku nedajú, vezme sa obrázok z videa.
      }
    }
    return video.value ? await createImageBitmap(video.value) : null
  }

  /** Zoznam kamier. Názvy prehliadač prezradí až po povolení kamery. */
  async function loadCameras (): Promise<void> {
    const devices = await navigator.mediaDevices.enumerateDevices()
    cameras.value = devices
      .filter(d => d.kind === 'videoinput')
      .map((d, i) => ({ value: d.deviceId, title: d.label || t('scan.cameraN', { n: i + 1 }) }))
  }

  async function start (): Promise<void> {
    error.value = null
    photoError.value = null
    if (!liveSupported.value) {
      error.value = t('scan.insecure')
      return
    }
    starting.value = true
    try {
      const detector = await getDetector()
      const known = cameraId.value && cameras.value.some(c => c.value === cameraId.value)
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          // Vybraná kamera, inak zadná na telefóne a ktorákoľvek na počítači.
          ...(cameraId.value && (known || cameras.value.length === 0)
            ? { deviceId: { exact: cameraId.value } }
            : { facingMode: { ideal: 'environment' } }),
          // Viac bodov = ostrejšie pruhy; webkamera dá, koľko vie.
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      })
      const track = stream.getVideoTracks()[0]
      // Priebežné ostrenie, kde ho kamera má. Kde nie, jednoducho sa nič nestane.
      await track?.applyConstraints({ advanced: [{ focusMode: 'continuous' } as MediaTrackConstraintSet] }).catch(() => {})
      await loadCameras()
      const active = track?.getSettings().deviceId ?? null
      if (active && active !== cameraId.value) cameraId.value = active

      if (!open.value || !video.value) {
        stop()
        return
      }
      video.value.srcObject = stream
      await video.value.play()
      starting.value = false
      live.value = true
      loop(detector)
    } catch (error_) {
      starting.value = false
      const name = (error_ as { name?: string }).name
      if (name === 'OverconstrainedError' && cameraId.value) {
        // Zapamätaná kamera už nie je pripojená: skúsiť ktorúkoľvek.
        cameraId.value = null
        return
      }
      error.value = name === 'NotAllowedError'
        ? t('scan.denied')
        : (name === 'NotFoundError' ? t('scan.noCamera') : t('scan.failed'))
      stop()
    }
  }

  /**
   * Päťkrát za sekundu stačí a procesor sa pritom nezadýcha. Pokusy sa
   * striedajú: celý záber, zväčšený stred (webkamera, čo nezaostrí)
   * a vyrovnaný tieň (lampa alebo ruka nad krabicou).
   */
  function loop (detector: Detector): void {
    timer = setTimeout(async () => {
      if (!open.value || !video.value || !stream) return
      try {
        // Striedavo celý záber, zväčšený stred a vyrovnaný tieň.
        tick++
        const source = tick % 3 === 1
          ? (enhancedCenter(video.value) ?? video.value)
          : (tick % 3 === 2 ? (flattened(video.value) ?? video.value) : video.value)
        const code = pickCode(await detector.detect(source))
        if (code) {
          finish(code)
          return
        }
      } catch {
        // Jeden nepodarený snímok nič neznamená, skúsi sa ďalší.
      }
      loop(detector)
    }, 200)
  }

  /** Prepnutie kamery: zastaviť starú, spustiť novú, zapamätať si výber. */
  watch(cameraId, (id, previous) => {
    saveCamera(id)
    if (open.value && stream && id !== previous) {
      const current = stream.getVideoTracks()[0]?.getSettings().deviceId
      if (current !== id) {
        stop()
        start()
      }
    } else if (open.value && !stream && id === null) {
      start()
    }
  })

  async function readBitmap (bitmap: ImageBitmap | null): Promise<void> {
    if (!bitmap) {
      photoError.value = t('scan.photoFailed')
      return
    }
    const code = await readStill(bitmap)
    bitmap.close()
    if (code) finish(code)
    else photoError.value = t('scan.photoNoCode')
  }

  /** Pri živom obraze snímka z neho, inak fotoaparát telefónu. */
  async function takePhoto (): Promise<void> {
    photoError.value = null
    if (!live.value) {
      openFile(true)
      return
    }
    readingPhoto.value = true
    try {
      await readBitmap(await grabFrame())
    } catch {
      photoError.value = t('scan.photoFailed')
    } finally {
      readingPhoto.value = false
    }
  }

  /** Súbor z disku; na telefóne s `camera` rovno fotoaparát. */
  function openFile (camera: boolean): void {
    photoError.value = null
    const input = photoInput.value
    if (!input) return
    if (camera) input.setAttribute('capture', 'environment')
    else input.removeAttribute('capture')
    input.click()
  }

  async function onPhoto (event: Event): Promise<void> {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    input.value = ''
    if (!file) return
    readingPhoto.value = true
    try {
      await readBitmap(await createImageBitmap(file))
    } catch {
      photoError.value = t('scan.photoFailed')
    } finally {
      readingPhoto.value = false
    }
  }

  watch(open, isOpen => {
    if (isOpen) start()
    else stop()
  })

  onBeforeUnmount(stop)
</script>

<template>
  <v-dialog v-model="open" max-width="600">
    <v-card>
      <v-card-title>{{ t('scan.title') }}</v-card-title>

      <v-card-text class="d-flex flex-column ga-3">
        <v-select
          v-if="cameras.length > 1"
          v-model="cameraId"
          density="compact"
          hide-details
          :items="cameras"
          :label="t('scan.chooseCamera')"
          prepend-inner-icon="mdi-webcam"
          variant="outlined"
        />

        <v-alert v-if="error" type="warning" variant="tonal">{{ error }}</v-alert>

        <div v-else class="scan-frame">
          <video ref="video" class="scan-video" muted playsinline />
          <div class="scan-line" />
          <v-progress-circular v-if="starting" class="scan-spinner" color="white" indeterminate />
        </div>

        <div class="text-caption text-medium-emphasis">{{ t('scan.hint') }}</div>

        <v-alert v-if="photoError" density="compact" type="info" variant="tonal">{{ photoError }}</v-alert>

        <input
          ref="photoInput"
          accept="image/*"
          class="d-none"
          type="file"
          @change="onPhoto"
        >
      </v-card-text>

      <v-card-actions>
        <v-btn
          :disabled="starting"
          :loading="readingPhoto"
          prepend-icon="mdi-camera-iris"
          variant="tonal"
          @click="takePhoto"
        >{{ t('scan.photo') }}</v-btn>

        <v-btn
          prepend-icon="mdi-image-outline"
          size="small"
          variant="text"
          @click="openFile(false)"
        >{{ t('scan.fromFile') }}</v-btn>

        <v-spacer />
        <v-btn variant="text" @click="open = false">{{ t('common.cancel') }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.scan-frame {
  aspect-ratio: 4 / 3;
  background: #000;
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.scan-video {
  height: 100%;
  object-fit: cover;
  width: 100%;
}

/* Vodiaca čiara: kód treba mať zhruba vodorovne v strede. */
.scan-line {
  background: rgba(208, 16, 18, 0.85);
  box-shadow: 0 0 8px rgba(208, 16, 18, 0.9);
  height: 2px;
  left: 10%;
  position: absolute;
  right: 10%;
  top: 50%;
}

.scan-spinner {
  left: 50%;
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
}
</style>
