<script setup lang="ts">
  /**
   * Pridanie setu. Po zadaní čísla sa dotiahnu metadáta a keď je set už
   * v zbierke, ukáže sa nad náhľadom výrazný pás, nie poznámka v texte.
   * Ak ide o zberateľskú sériu, namiesto jedného náhľadu príde mriežka
   * členov, lebo z čísla na sáčku sa nedá zistiť, ktorá figúrka je vnútri.
   *
   * Kategórie sa vyberajú hneď tu. Predvybrané sú tie, ktorých pravidlo na
   * set sedí, a zmeny sa zapíšu až po uložení kusov, takže zrušené pridanie
   * nezanechá v kategóriách nič.
   *
   * Jedno pole na číslo z krabice aj čiarový kód: 12 až 13 číslic so
   * sediacou kontrolnou číslicou je kód, všetko ostatné číslo setu. Kód sa
   * dá napísať, nasnímať kamerou (ikona v poli) alebo načítať ručnou
   * čítačkou, ktorá sa správa ako klávesnica. Hľadanie kódu kvótu nemíňa.
   *
   * Skenovanie kopy krabíc (scanner/scanFlow.ts): rovnaký kód znova je
   * ďalší kus, iný kód uloží rozpracovaný set tak, ako je vo formulári,
   * a načíta nový. Automatické uloženie sa dá vrátiť tlačidlom Späť
   * v oznámení. Skeny sa spracúvajú po jednom, v poradí príchodu, aby sa
   * pri rýchlom skenovaní nič neuložilo dvakrát. Sken z inej obrazovky sem
   * príde cez `?code=` (AppLayout).
   */
  import type { CatalogCategory, CatalogDetail, ItemCondition, ItemPurpose } from '@/api/types'
  import { computed, onMounted, ref } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useRoute, useRouter } from 'vue-router'
  import { api, errorMessage } from '@/api/client'
  import { CONDITIONS, FLAGS, PURPOSES } from '@/api/types'
  import BarcodeScanner from '@/components/BarcodeScanner.vue'
  import CategoryManager from '@/components/CategoryManager.vue'
  import DateField from '@/components/DateField.vue'
  import KeyHint from '@/components/KeyHint.vue'
  import PlaceFields from '@/components/PlaceFields.vue'
  import SetImage from '@/components/SetImage.vue'
  import { useFormMemory } from '@/composables/useFormMemory'
  import { saveWithFollowups, undoCreated } from '@/scanner/saveFlow'
  import { decideScan } from '@/scanner/scanFlow'
  import { createScanQueue } from '@/scanner/scanQueue'
  import { useScanCodes } from '@/scanner/useScanCodes'
  import { useAuthStore } from '@/stores/auth'
  import { useCollectionStore } from '@/stores/collection'
  import { useNotifyStore } from '@/stores/notify'
  import { useScannerStore } from '@/stores/scanner'
  import { isBarcode } from '@/utils/barcode'
  import { count, exactMoney, isoDate, money, shortDate, toNumber } from '@/utils/format'
  import { imageSrc } from '@/utils/imageSrc'

  const { t } = useI18n()
  const router = useRouter()
  const route = useRoute()
  const collection = useCollectionStore()
  const notify = useNotifyStore()
  const auth = useAuthStore()
  const memory = useFormMemory()
  const scanner = useScannerStore()
  // Našepkávače (kde uložené, kde kúpené) môžu byť prázdne, keď sa sem prišlo priamo.
  if (collection.purchasePlaces.length === 0 && collection.locations.length === 0) collection.loadLocations()

  const setNumber = ref('')
  /** Ako hľadať: číslom z krabice, alebo čiarovým kódom. */
  const scanOpen = ref(false)
  /** Vysvetlenie, prečo sa kód nenašiel, a čo s tým. */
  const eanMessage = ref<string | null>(null)
  /**
   * Kód, ktorý nikto nepoznal. Po uložení sa priradí setu zadanému číslom,
   * takže ďalší sken ho nájde doma. Katalóg je spoločný, pomôže to aj otcovi.
   */
  const pendingEan = ref<string | null>(null)
  /** Kód, ktorým sa načítal zobrazený set (null pri zadaní číslom). */
  const foundCode = ref<string | null>(null)
  /** Neúspech je zapamätaný z hľadania v tento deň; dá sa skúsiť znova. */
  const eanCachedAt = ref<string | null>(null)
  const searching = ref(false)
  const saving = ref(false)
  const notFound = ref(false)
  const error = ref<string | null>(null)
  const found = ref<CatalogDetail | null>(null)

  const quantity = ref(1)
  const condition = ref<ItemCondition>('new_sealed')
  const price = ref('')
  const purchaseDate = ref(isoDate())
  const place = ref<string | null>('')
  const location = ref<string | null>('')
  const box = ref<string | null>('')
  const purpose = ref<ItemPurpose | null>(null)
  const note = ref('')
  const flags = ref<string[]>(['has_box', 'has_manual'])

  /** Kategórie z pohľadu nájdeného setu a to, čo v nich má byť po uložení. */
  const categoryRows = ref<CatalogCategory[]>([])
  const chosenCategories = ref<number[]>([])
  const managerOpen = ref(false)

  const memberCounts = ref<Record<string, number>>({})
  const sealedBag = ref(false)

  // Ručné zadanie pre sety, ktoré katalóg nepozná, alebo keď nie sú API kľúče.
  const manualOpen = ref(false)
  const manual = ref({
    name: '',
    year: '' as string | number,
    theme: '',
    num_parts: '' as string | number,
    rrp_eur: '',
  })

  /**
   * Bez kľúča Rebrickable appka set nedohľadá (názov, fotka, téma). Set sa
   * dá uložiť ručne len číslom a appka odporučí kľúč pripojiť.
   */
  const noCatalog = computed(() => !auth.can('rebrickable.set'))

  const isSeries = computed(() => (found.value?.members?.length ?? 0) > 1)
  const ownership = computed(() => found.value?.ownership ?? null)

  const selectedMembers = computed(() =>
    Object.entries(memberCounts.value)
      .filter(([, n]) => n > 0)
      .map(([catalog_num, n]) => ({ catalog_num, quantity: n })),
  )

  const totalPieces = computed(() => {
    if (sealedBag.value) return quantity.value
    if (isSeries.value) return selectedMembers.value.reduce((sum, m) => sum + m.quantity, 0)
    return quantity.value
  })

  const totalCost = computed(() => {
    const unit = toNumber(price.value)
    if (unit === null) return null
    return unit * totalPieces.value
  })

  const canSubmit = computed(() => found.value !== null && totalPieces.value > 0 && !saving.value)

  /**
   * Načíta kategórie pre nájdený set. Po úprave kategórií v správcovi ostane
   * výber, ktorý už používateľ urobil; nové kategórie prídu s návrhom z pravidla.
   */
  async function loadCategoryRows (keepChoice = false): Promise<void> {
    if (!found.value) return
    const { data } = await api.GET('/catalog/{num}/categories', {
      params: { path: { num: found.value.catalog_num } },
    })
    const known = new Set(categoryRows.value.map(r => r.id))
    const previous = new Set(chosenCategories.value)
    categoryRows.value = data ?? []
    chosenCategories.value = categoryRows.value
      .filter(r => (keepChoice && known.has(r.id) ? previous.has(r.id) : r.member))
      .map(r => r.id)
  }

  /** Zapíše len rozdiely oproti tomu, čo by platilo samo od seba. */
  async function applyCategories (num: string): Promise<void> {
    const chosen = new Set(chosenCategories.value)
    for (const row of categoryRows.value) {
      if (chosen.has(row.id) === row.member) continue
      await api.PUT('/categories/{category_id}/members/{num}', {
        params: { path: { category_id: row.id, num } },
        body: { member: chosen.has(row.id) },
      })
    }
  }

  function resetFound (): void {
    notFound.value = false
    error.value = null
    eanMessage.value = null
    eanCachedAt.value = null
    found.value = null
    foundCode.value = null
    memberCounts.value = {}
    sealedBag.value = false
    categoryRows.value = []
    chosenCategories.value = []
  }

  /** Nájdený set (číslom aj kódom) sa ďalej spracuje rovnako. */
  async function applyFound (data: CatalogDetail): Promise<void> {
    found.value = data
    for (const member of data.members ?? []) {
      memberCounts.value[member.catalog_num] = 0
    }
    await loadCategoryRows()
  }

  async function lookup (): Promise<void> {
    const num = setNumber.value.trim()
    if (!num) return
    searching.value = true
    resetFound()
    try {
      const { data, error: err } = await api.GET('/catalog/{num}', {
        params: { path: { num } },
      })
      if (err || !data) {
        notFound.value = true
        // Bez katalógu je ručné zadanie jediná cesta, netreba naň klikať.
        if (noCatalog.value) manualOpen.value = true
        return
      }
      await applyFound(data)
    } catch (error_) {
      error.value = errorMessage(error_)
    } finally {
      searching.value = false
    }
  }

  /** Jedno tlačidlo Nájsť: čiarový kód, alebo číslo setu. */
  function search (): Promise<void> {
    return isBarcode(setNumber.value) ? lookupEan(setNumber.value) : lookup()
  }

  async function lookupEan (raw: string, retry = false): Promise<void> {
    const code = raw.replace(/\D/g, '')
    if (!code) return
    searching.value = true
    resetFound()
    pendingEan.value = null
    try {
      const { data, error: err } = await api.GET('/catalog/by-ean/{code}', {
        params: { path: { code }, query: retry ? { retry: true } : {} },
      })
      if (err || !data) {
        eanMessage.value = errorMessage(err, t('scan.invalid'))
        return
      }
      if (data.catalog) {
        await applyFound(data.catalog)
        foundCode.value = data.ean
        return
      }
      pendingEan.value = data.ean
      eanMessage.value = eanOutcomeMessage(data.outcome, data.product_title)
      eanCachedAt.value = data.cached ? (data.checked_at ?? null) : null
    } catch (error_) {
      error.value = errorMessage(error_)
    } finally {
      searching.value = false
    }
  }

  /** Prečo sa set podľa kódu nenašiel, po slovensky. */
  function eanOutcomeMessage (outcome: string, title?: string | null): string {
    switch (outcome) {
      case 'limit': { return t('scan.limit') }
      case 'disabled': { return t('scan.disabled') }
      case 'no_set_number': { return t('scan.noSetNumber', { title: title ?? '' }) }
      default: { return t('scan.notFound') }
    }
  }

  function onScanned (code: string): void {
    enqueue(() => handleScan(code))
  }

  /*
   * Skeny (čítačka, kamera, ?code= z inej obrazovky) aj uloženie tlačidlom
   * idú jeden za druhým. Bez fronty by rýchly druhý sken prišiel počas
   * ukladania prvého a set by sa uložil dvakrát alebo vôbec.
   */
  const queue = createScanQueue(error_ => notify.error(error_, t('notice.saveFailed')))
  const enqueue = queue.enqueue

  async function handleScan (code: string): Promise<void> {
    const decision = decideScan({ code: foundCode.value, pending: found.value !== null }, code)
    if (decision === 'increment' && found.value) {
      if (isSeries.value && !sealedBag.value) {
        // Druhý sken sáčku série: sú to nerozbalené sáčky, prvý sa ráta.
        sealedBag.value = true
        quantity.value = 2
      } else {
        quantity.value = Math.min(99, quantity.value + 1)
      }
      notify.info(t('scan.counted', { name: found.value.name, count: quantity.value }))
      return
    }
    if (decision === 'save-and-load' && !(await autoSave())) {
      return
    }
    setNumber.value = code
    await search()
  }

  // Ručná čítačka: kód prepíše pole celý, aj keď v ňom niečo bolo.
  useScanCodes(onScanned)

  /** Kód nepoznáme: pole sa uvoľní na číslo z krabice, je vytlačené veľkým písmom. */
  function useNumberInstead (): void {
    setNumber.value = ''
    eanMessage.value = null
  }

  async function saveManualCatalog (): Promise<void> {
    const num = setNumber.value.trim()
    if (!num) return
    saving.value = true
    error.value = null
    try {
      const { data, error: err } = await api.POST('/catalog', {
        body: {
          catalog_num: num,
          // Bez názvu ho server pomenuje „Set 10294“.
          name: manual.value.name.trim() || null,
          kind: 'set',
          year: manual.value.year ? Number(manual.value.year) : null,
          theme: manual.value.theme.trim() || null,
          num_parts: manual.value.num_parts ? Number(manual.value.num_parts) : null,
          rrp_eur: manual.value.rrp_eur ? String(Number(manual.value.rrp_eur)) : null,
          num_minifigs: null,
          image_url: null,
        },
      })
      if (err || !data) {
        error.value = errorMessage(err, 'Set sa nepodarilo uložiť')
        return
      }
      notify.success(t('notice.catalogSaved', { num }))
      manualOpen.value = false
      notFound.value = false
      await lookup()
    } finally {
      saving.value = false
    }
  }

  function selectAllMembers (): void {
    for (const key of Object.keys(memberCounts.value)) memberCounts.value[key] = 1
  }

  function clearMembers (): void {
    for (const key of Object.keys(memberCounts.value)) memberCounts.value[key] = 0
  }

  function bump (num: string, delta: number): void {
    const next = (memberCounts.value[num] ?? 0) + delta
    memberCounts.value[num] = Math.max(0, Math.min(99, next))
  }

  /**
   * Uloží, čo je vo formulári, a vráti id vytvorených kusov (na Späť).
   * Kategórie, neznámy kód a pamäť formulára sa zapíšu tu, pri tlačidle
   * aj pri automatickom uložení po skene.
   */
  async function saveCurrent (): Promise<number[]> {
    if (!found.value) return []
    const shared = {
      condition: condition.value,
      flags: flags.value,
      purchase_price_eur: price.value ? String(toNumber(price.value)) : null,
      purchase_date: purchaseDate.value || null,
      purchase_place: (place.value ?? '').trim() || null,
      location: (location.value ?? '').trim() || null,
      box: (box.value ?? '').trim() || null,
      purpose: purpose.value,
    }
    const num = found.value.catalog_num
    const create = async (): Promise<number[]> => {
      const result = isSeries.value && !sealedBag.value
        ? await api.POST('/items/bulk', {
          body: { ...shared, members: selectedMembers.value, price_variant: 'sealed' } as never,
        })
        : await api.POST('/items', {
          body: {
            ...shared,
            catalog_num: num,
            quantity: quantity.value,
            unidentified: sealedBag.value,
            price_variant: sealedBag.value ? 'sealed' : null,
            note: note.value.trim() || null,
          } as never,
        })
      if (result.error) throw new Error(errorMessage(result.error, t('notice.saveFailed')))
      return (result.data ?? []).map(item => item.id)
    }
    const ean = pendingEan.value
    // Kusy vznikli: zlyhaná kategória alebo kód sa ohlási, ale uloženie
    // platí, inak by ďalší sken ten istý set uložil znova.
    const ids = await saveWithFollowups(create, [
      // Pri sérii sa kategória lepí na sériu a prenesie sa na jej figúrky.
      () => applyCategories(num),
      async () => {
        if (!ean) return
        const { error: err } = await api.PUT('/catalog/{num}/ean', {
          params: { path: { num } },
          body: { ean },
        })
        if (err) throw new Error(errorMessage(err, t('notice.saveFailed')))
      },
    ], error_ => notify.error(error_, t('notice.followupFailed')))
    pendingEan.value = null
    memory.remember({
      location: location.value ?? '',
      box: box.value ?? '',
      condition: condition.value,
      purpose: purpose.value,
      place: place.value ?? '',
      date: purchaseDate.value,
    })
    return ids
  }

  /**
   * Sken iného kódu: rozpracovaný set sa uloží tak, ako je. Vráti false,
   * keď sa uložiť nepodarilo; vtedy sa nový kód nenačíta, nech sa
   * rozpracovaný set nestratí.
   */
  async function autoSave (): Promise<boolean> {
    if (!found.value) return true
    const name = found.value.name
    const num = found.value.catalog_num
    const pieces = totalPieces.value
    if (pieces === 0) {
      notify.warn(t('notice.seriesNotSaved', { name }))
      return true
    }
    saving.value = true
    try {
      const ids = await saveCurrent()
      notify.success(t('notice.autoSaved', { num, name, count: pieces }), {
        label: t('notice.undo'),
        run: () => undoSave(ids),
      })
    } catch (error_) {
      notify.error(error_, t('notice.saveFailed'))
      return false
    } finally {
      saving.value = false
    }
    // Ďalšia krabica býva z tej istej kopy: stav, miesto, dátum a čipy ostanú.
    quantity.value = 1
    price.value = ''
    note.value = ''
    collection.refreshAll()
    return true
  }

  /** Späť po automatickom uložení: zmaže práve tie kusy, nič iné. */
  async function undoSave (ids: number[]): Promise<void> {
    const failed = await undoCreated(ids, async id => {
      const { error: err } = await api.DELETE('/items/{item_id}', { params: { path: { item_id: id } } })
      return !err
    })
    if (failed > 0) notify.error(t('notice.undoFailed'))
    else notify.success(t('notice.undone'))
    collection.refreshAll()
  }

  function submit (): Promise<void> {
    return enqueue(async () => {
      if (!found.value) return
      const name = found.value.name
      const pieces = totalPieces.value
      saving.value = true
      error.value = null
      try {
        await saveCurrent()
        // Uložené: set už nie je rozpracovaný, sken čakajúci vo fronte ho
        // nesmie uložiť druhý raz.
        resetFound()
        setNumber.value = ''
        notify.success(t('notice.addedPieces', { name, count: pieces }))
        // Keď medzitým prišiel sken, ostáva sa tu a načíta sa; inak do Zbierky.
        if (queue.waiting() === 0) {
          await collection.refreshAll()
          router.push({ name: 'collection' })
        } else {
          collection.refreshAll()
        }
      } catch (error_) {
        error.value = error_ instanceof Error ? error_.message : errorMessage(error_, t('notice.saveFailed'))
      } finally {
        saving.value = false
      }
    })
  }

  onMounted(() => {
    // Najprv pamäť formulára, potom skeny, všetko v jednej fronte: sken,
    // ktorý príde počas načítania pamäte, sa spracuje až po nej.
    enqueue(async () => {
      await memory.load()
      const start = memory.initial()
      condition.value = start.condition
      purchaseDate.value = start.date
      place.value = start.place
      location.value = start.location
      box.value = start.box
      purpose.value = start.purpose
    })
    // Skeny z iných obrazoviek (aj viac naraz počas otvárania) v poradí.
    const code = typeof route.query.code === 'string' ? route.query.code : null
    if (code) router.replace({ query: {} })
    for (const waiting of [...(code ? [code] : []), ...scanner.drain()]) onScanned(waiting)
  })
</script>

<template>
  <div class="mx-auto d-flex flex-column ga-4" style="max-width: 920px">
    <v-alert
      v-if="error"
      closable
      type="error"
      variant="tonal"
      @click:close="error = null"
    >
      {{ error }}
    </v-alert>

    <!-- Odpoveď na otázku "mám to už?" musí byť vidieť na prvý pohľad. -->
    <v-alert
      v-if="ownership?.owned"
      border="start"
      color="secondary"
      icon="mdi-information-outline"
      prominent
      variant="tonal"
    >
      <div class="text-subtitle-1 font-weight-bold">{{ t('add.alreadyOwned') }}</div>

      <div class="text-body-2">
        {{ t('add.alreadyOwnedDetail', {
          count: t('collection.pieces', { count: ownership.owned_count }),
          locations: ownership.locations.join(', ') || '—',
          price: exactMoney(ownership.last_purchase_price),
        }) }}
      </div>

      <template #append>
        <v-btn
          size="small"
          :to="{ name: 'set-detail', params: { num: found?.catalog_num } }"
          variant="text"
        >{{ t('add.showInCollection') }}</v-btn>
      </template>
    </v-alert>

    <v-alert
      v-if="noCatalog"
      border="start"
      icon="mdi-database-off-outline"
      type="warning"
      variant="tonal"
    >
      <div class="text-high-emphasis">
        <div class="text-subtitle-2">{{ t('add.noCatalogTitle') }}</div>
        <div class="text-body-2">{{ t('add.noCatalogText') }}</div>
      </div>

      <v-btn
        class="mt-2 ms-n3"
        prepend-icon="mdi-key-outline"
        size="small"
        :to="{ name: 'settings', query: { tab: 'data' } }"
        variant="text"
      >{{ t('add.noCatalogConnect') }}</v-btn>
    </v-alert>

    <v-card border class="pa-4 d-flex flex-column ga-3" flat>
      <div class="d-flex ga-3 align-start">
        <v-text-field
          v-model="setNumber"
          autofocus
          class="flex-grow-1"
          :hint="t('add.hintAny')"
          :label="t('add.setNumberOrBarcode')"
          persistent-hint
          @keyup.enter="search"
        >
          <template #append-inner>
            <v-btn
              density="comfortable"
              icon="mdi-barcode-scan"
              size="small"
              :title="t('scan.camera')"
              variant="text"
              @click="scanOpen = true"
            />
          </template>
        </v-text-field>

        <v-btn
          color="primary"
          :loading="searching"
          prepend-icon="mdi-magnify"
          size="large"
          @click="search"
        >{{ t('add.find') }}</v-btn>
      </div>

      <div class="text-caption text-medium-emphasis">
        <v-icon class="me-1" icon="mdi-barcode-scan" size="small" />{{ t('scan.wedgeReady') }}. {{ t('scan.wedgeHint') }}
      </div>

      <v-chip
        v-if="pendingEan"
        class="align-self-start"
        closable
        label
        prepend-icon="mdi-barcode"
        variant="tonal"
        @click:close="pendingEan = null"
      >{{ t('scan.willRemember', { code: pendingEan }) }}</v-chip>

      <v-alert v-if="eanMessage" type="info" variant="tonal">
        {{ eanMessage }}
        <KeyHint
          v-if="!auth.can('brickset.barcode') || !auth.can('upcitemdb.barcode')"
          class="mt-1"
          service="brickset"
          :text="t('keyHint.barcode')"
        />

        <div v-if="eanCachedAt" class="text-caption mt-1">
          {{ t('scan.cached', { date: shortDate(eanCachedAt) }) }}
        </div>

        <template #append>
          <div class="d-flex flex-column ga-1">
            <v-btn size="small" variant="text" @click="useNumberInstead">{{ t('scan.useNumber') }}</v-btn>

            <v-btn
              v-if="eanCachedAt && pendingEan"
              :loading="searching"
              prepend-icon="mdi-refresh"
              size="small"
              variant="text"
              @click="lookupEan(pendingEan, true)"
            >{{ t('scan.retry') }}</v-btn>
          </div>
        </template>
      </v-alert>

      <v-alert v-if="notFound && !manualOpen" type="info" variant="tonal">
        {{ t('add.notFound') }}
        <template #append>
          <v-btn size="small" variant="tonal" @click="manualOpen = true">
            {{ t('add.manualEntry') }}
          </v-btn>
        </template>
      </v-alert>

      <!-- Bez API kľúčov alebo pri neznámom sete sa set zadá ručne. -->
      <v-card v-if="manualOpen" class="pa-3 d-flex flex-column ga-3" color="surface-variant" flat>
        <div class="text-subtitle-1">{{ t('add.manualTitle') }}</div>
        <v-text-field v-model="manual.name" autofocus :label="t('add.manualName')" />

        <v-row dense>
          <v-col cols="6" sm="3">
            <v-text-field v-model="manual.year" :label="t('add.manualYear')" type="number" />
          </v-col>

          <v-col cols="6" sm="3">
            <v-text-field v-model="manual.theme" :label="t('add.manualTheme')" />
          </v-col>

          <v-col cols="6" sm="3">
            <v-text-field v-model="manual.num_parts" :label="t('add.manualParts')" type="number" />
          </v-col>

          <v-col cols="6" sm="3">
            <v-text-field
              v-model="manual.rrp_eur"
              :label="t('add.manualRrp')"
              prefix="€"
              type="number"
            />
          </v-col>
        </v-row>

        <div class="d-flex ga-2">
          <v-spacer />
          <v-btn variant="text" @click="manualOpen = false">{{ t('common.cancel') }}</v-btn>

          <v-btn
            color="primary"
            :disabled="!setNumber.trim()"
            :loading="saving"
            variant="flat"
            @click="saveManualCatalog"
          >{{ t('settings.save') }}</v-btn>
        </div>
      </v-card>

      <v-card v-if="found" class="pa-3" color="surface-variant" flat>
        <div class="d-flex ga-4 flex-wrap">
          <SetImage
            :alt="found.name"
            rounded="md"
            :size="116"
            :src="imageSrc(found.image_url) ?? undefined"
            style="width: 116px"
          />

          <div class="flex-grow-1" style="min-width: 240px">
            <div class="d-flex align-start ga-2">
              <div>
                <div class="text-h6">{{ found.name }}</div>

                <div class="text-body-2 text-medium-emphasis">
                  {{ found.catalog_num }}<span v-if="found.theme"> · {{ found.theme }}</span>
                  <span v-if="found.year"> · {{ found.year }}</span>
                </div>
              </div>

              <v-chip
                v-if="found.is_retired"
                class="ms-auto"
                color="secondary"
                label
                size="small"
                variant="flat"
              >{{ found.retired_at ? t('detail.retired', { year: found.retired_at }) : t('detail.retiredShort') }}</v-chip>
            </div>

            <v-row class="mt-1" dense>
              <v-col cols="6" sm="3">
                <div class="text-caption text-medium-emphasis">{{ t('detail.parts') }}</div>
                <div class="text-body-2 font-weight-medium">{{ count(found.num_parts) }}</div>
              </v-col>

              <v-col cols="6" sm="3">
                <div class="text-caption text-medium-emphasis">{{ t('detail.minifigs') }}</div>
                <div class="text-body-2 font-weight-medium">{{ count(found.num_minifigs) }}</div>
              </v-col>

              <v-col cols="6" sm="3">
                <div class="text-caption text-medium-emphasis">{{ t('detail.rrp') }}</div>
                <div class="text-body-2 font-weight-medium">{{ exactMoney(found.rrp_eur) }}</div>
              </v-col>

              <v-col cols="6" sm="3">
                <div class="text-caption text-medium-emphasis">{{ t('collection.status.owned') }}</div>
                <div class="text-body-2 font-weight-medium">{{ ownership?.owned_count ?? 0 }}</div>
              </v-col>
            </v-row>
          </div>
        </div>
      </v-card>
    </v-card>

    <!-- Zberateľská séria: z čísla sáčku sa nedá zistiť, ktorá figúrka je vnútri. -->
    <v-card v-if="isSeries" border class="pa-4 d-flex flex-column ga-3" flat>
      <div class="d-flex align-center ga-3 flex-wrap">
        <div>
          <div class="text-h6">{{ t('add.seriesTitle') }}</div>

          <div class="text-body-2 text-medium-emphasis">
            {{ t('add.seriesHint', { count: found?.members?.length ?? 0 }) }}
          </div>
        </div>

        <div class="ms-auto d-flex ga-2">
          <v-btn size="small" variant="outlined" @click="selectAllMembers">
            {{ t('add.selectAll') }}
          </v-btn>

          <v-btn size="small" variant="text" @click="clearMembers">
            {{ t('add.clearSelection') }}
          </v-btn>
        </div>
      </div>

      <v-checkbox
        v-model="sealedBag"
        density="comfortable"
        hide-details
        :label="t('add.sealedBag')"
        :messages="t('add.sealedBagHint')"
      />

      <v-row v-if="!sealedBag" dense>
        <v-col
          v-for="member in found?.members ?? []"
          :key="member.catalog_num"
          cols="6"
          md="3"
          sm="4"
        >
          <v-card
            border
            class="pa-2 text-center"
            :color="memberCounts[member.catalog_num] ? 'primary-container' : undefined"
            flat
          >
            <SetImage :alt="member.name" rounded="md" :size="72" :src="imageSrc(member.image_url) ?? undefined" />
            <div class="text-caption mt-1 text-truncate">{{ member.name }}</div>

            <div class="d-flex align-center justify-center ga-1 mt-1">
              <v-btn
                density="comfortable"
                icon="mdi-minus"
                size="small"
                variant="text"
                @click="bump(member.catalog_num, -1)"
              />

              <span class="text-body-2 font-weight-medium" style="min-width: 18px">
                {{ memberCounts[member.catalog_num] ?? 0 }}
              </span>

              <v-btn
                density="comfortable"
                icon="mdi-plus"
                size="small"
                variant="text"
                @click="bump(member.catalog_num, 1)"
              />
            </div>
          </v-card>
        </v-col>
      </v-row>

      <div v-if="!sealedBag" class="text-body-2 text-medium-emphasis">
        {{ t('add.selectedCount', { count: totalPieces }) }}
      </div>
    </v-card>

    <v-card v-if="found" border class="pa-4 d-flex flex-column ga-4" flat>
      <div class="text-h6">{{ t('add.yourData') }}</div>

      <v-row dense>
        <v-col v-if="!isSeries || sealedBag" cols="12" md="3" sm="4">
          <v-text-field
            v-model.number="quantity"
            :label="t('add.quantity')"
            max="99"
            min="1"
            type="number"
          />
        </v-col>

        <v-col cols="12" md="4" sm="4">
          <v-select
            v-model="condition"
            item-title="title"
            item-value="value"
            :items="CONDITIONS.map(c => ({ value: c, title: t(`condition.${c}`) }))"
            :label="t('add.condition')"
          />
        </v-col>

        <v-col cols="12" md="5" sm="4">
          <v-text-field
            v-model="price"
            :hint="t('add.perPiece')"
            :label="t('add.purchasePrice')"
            persistent-hint
            prefix="€"
            type="number"
          />
        </v-col>
      </v-row>

      <v-row dense>
        <v-col cols="12" md="6">
          <DateField
            v-model="purchaseDate"
            clearable
            :label="t('add.purchaseDate')"
          />
        </v-col>

        <v-col cols="12" md="6">
          <v-combobox v-model="place" :items="collection.purchasePlaces" :label="t('add.purchasePlace')" prepend-inner-icon="mdi-storefront-outline" />
        </v-col>

        <v-col cols="12">
          <PlaceFields v-model:box="box" v-model:location="location" />
        </v-col>
      </v-row>

      <div>
        <div class="text-body-2 text-medium-emphasis mb-2">{{ t('purpose.label') }}</div>

        <v-chip-group v-model="purpose" column filter>
          <v-chip
            v-for="value in PURPOSES"
            :key="value"
            label
            :value="value"
            variant="outlined"
          >{{ t(`purpose.${value}`) }}</v-chip>
        </v-chip-group>
      </div>

      <div>
        <div class="text-body-2 text-medium-emphasis mb-2">{{ t('add.flags') }}</div>

        <v-chip-group v-model="flags" column filter multiple>
          <v-chip
            v-for="flag in FLAGS"
            :key="flag"
            size="large"
            :value="flag"
            variant="outlined"
          >
            {{ t(`flag.${flag}`) }}
          </v-chip>
        </v-chip-group>
      </div>

      <div>
        <div class="d-flex align-center ga-2 mb-1">
          <span class="text-body-2 text-medium-emphasis">{{ t('add.categories') }}</span>
          <v-spacer />

          <v-btn
            prepend-icon="mdi-cog-outline"
            size="small"
            variant="text"
            @click="managerOpen = true"
          >{{ t('filters.manage') }}</v-btn>
        </div>

        <div class="text-caption text-medium-emphasis mb-2">
          {{ isSeries ? t('add.categoriesHintSeries') : t('add.categoriesHint') }}
        </div>

        <v-chip-group
          v-if="categoryRows.length > 0"
          v-model="chosenCategories"
          column
          filter
          multiple
        >
          <v-chip
            v-for="row in categoryRows"
            :key="row.id"
            label
            :title="row.reason === 'rule' ? t('categories.viaRule') : undefined"
            :value="row.id"
            variant="outlined"
          >
            <span class="add-cat-dot me-2" :class="`bg-${row.color ?? 'grey'}`" />
            {{ row.name }}
            <v-icon v-if="row.reason === 'rule'" class="ms-1" icon="mdi-auto-fix" size="x-small" />
          </v-chip>
        </v-chip-group>

        <div v-else class="text-body-2 text-medium-emphasis">{{ t('categories.empty') }}</div>
      </div>

      <v-textarea v-model="note" :label="t('add.note')" rows="2" />
    </v-card>

    <div v-if="found" class="d-flex align-center ga-3 flex-wrap">
      <span class="text-body-2 text-medium-emphasis">
        {{ t('add.willCreate', {
          count: t('collection.pieces', { count: totalPieces }),
          total: totalCost !== null ? money(totalCost) : '—',
        }) }}
      </span>

      <v-spacer />
      <v-btn variant="text" @click="$router.back()">{{ t('add.cancel') }}</v-btn>

      <v-btn
        color="primary"
        :disabled="!canSubmit"
        :loading="saving"
        prepend-icon="mdi-plus"
        size="large"
        @click="submit"
      >{{ t('add.submit') }}</v-btn>
    </div>

    <CategoryManager v-model="managerOpen" @changed="loadCategoryRows(true)" />

    <BarcodeScanner v-model="scanOpen" @detected="onScanned" />
  </div>
</template>

<style scoped>
.add-cat-dot {
  border-radius: 50%;
  display: inline-block;
  height: 8px;
  width: 8px;
}
</style>
