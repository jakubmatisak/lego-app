<script setup lang="ts">
  /**
   * Zásady ochrany súkromia (GDPR, čl. 13). Verejná stránka, bez prihlásenia.
   *
   * Prevádzkovateľa (meno a kontakt) vyplní správca v Nastaveniach →
   * Aplikácia. Text zodpovedá tomu, čo appka naozaj robí: pri zmene
   * spracúvania treba upraviť text aj `privacy_version` na serveri.
   */
  import { computed, onMounted } from 'vue'
  import { useI18n } from 'vue-i18n'
  import { useAuthStore } from '@/stores/auth'

  interface Section { title: string, body: string[] }

  const { locale, t } = useI18n()
  const auth = useAuthStore()

  onMounted(() => {
    auth.loadProviders()
  })

  const operatorName = computed(() => auth.providers?.operator_name ?? null)
  const operatorEmail = computed(() => auth.providers?.operator_email ?? null)
  const version = computed(() => auth.providers?.privacy_version ?? '')

  const SK: Section[] = [
    {
      title: 'Aké údaje spracúvame',
      body: [
        'Údaje účtu: e-mail, meno (ak ho zadáš), heslo uložené len ako odtlačok (argon2), jazyk a nastavenia zobrazenia.',
        'Tvoja zbierka: kusy, kúpne a predajné ceny, dátumy, umiestnenie, poznámky, zoznam Chcem, kategórie, uložené pohľady, odkazy na pozretie, overené ceny a ručne zadané ceny.',
        'Tvoje fotky kusov. Pri nahratí sa zmenšia a zmažú sa z nich údaje fotoaparátu vrátane polohy GPS.',
        'Kľúče k službám, ktoré si sám vložíš (Rebrickable, Brickset, BrickEconomy). Ukladajú sa zašifrované a nikdy sa nezobrazia celé.',
        'Záznam volaní cudzích služieb (čo, kedy, s akým výsledkom) 30 dní a prihlasovacie tokeny najviac 30 dní (pozri Ako dlho).',
      ],
    },
    {
      title: 'Prečo a na akom základe',
      body: [
        'Aby appka mohla viesť tvoju evidenciu: plnenie zmluvy, čl. 6 ods. 1 písm. b GDPR.',
        'Záznam volaní a tokeny kvôli bezpečnosti a stráženiu denných limitov služieb: oprávnený záujem, čl. 6 ods. 1 písm. f GDPR.',
        'Appka nepoužíva reklamu, analytiku ani sledovanie a údaje nepredáva.',
      ],
    },
    {
      title: 'Ako dlho',
      body: [
        'Údaje účtu a zbierky, kým účet nezmažeš. Záznam volaní 30 dní.',
        'Prihlásenie do zatvorenia prehliadača, na serveri najviac 12 hodín bez použitia. Keď pri prihlásení zaškrtneš Zapamätať si prihlásenie, 30 dní od posledného použitia. Odhlásenie ho zruší hneď.',
        'Pred každou aktualizáciou appky na inú verziu sa celá databáza zálohuje na server do priečinka backups. Uchováva sa 5 posledných záloh, staršie sa mažú. Údaje zmazaného účtu v nich môžu ostať, kým sa zálohy neprestriedajú.',
      ],
    },
    {
      title: 'Kto ich dostane',
      body: [
        'Poskytovateľ hostingu, na ktorom appka beží.',
        'Služby, ktoré si pripojíš vlastným kľúčom, dostanú len čísla setov a čiarové kódy, na ktoré sa pýtaš, nie tvoje osobné údaje. Eurostat nedostane nič, čo by sa ťa týkalo.',
        'Fotky setov sa načítavajú cez server appky, takže Rebrickable ani Brickset nevidia tvoju IP adresu.',
      ],
    },
    {
      title: 'Tvoje práva',
      body: [
        'Prístup a prenosnosť: v Nastaveniach → Účet si stiahneš všetky svoje údaje aj fotky (ZIP).',
        'Oprava: údaje zmeníš priamo v appke.',
        'Vymazanie: v Nastaveniach → Účet zmažeš účet so všetkým, čo k nemu patrí. V zálohách pred aktualizáciou ostane, kým sa neprestriedajú (pozri Ako dlho).',
        'Námietka a obmedzenie spracúvania: napíš prevádzkovateľovi.',
        'Sťažnosť: Úrad na ochranu osobných údajov Slovenskej republiky, dataprotection.gov.sk.',
      ],
    },
  ]

  const EN: Section[] = [
    {
      title: 'What data we process',
      body: [
        'Account data: e-mail, name (if you enter it), password stored only as a hash (argon2), language and display settings.',
        'Your collection: pieces, purchase and sale prices, dates, location, notes, wishlist, categories, saved views, share links, price checks and manually entered prices.',
        'Your photos of pieces. On upload they are shrunk and camera data including the GPS location is removed.',
        'Keys to services you add yourself (Rebrickable, Brickset, BrickEconomy). They are stored encrypted and never shown in full.',
        'A log of calls to external services (what, when, with what result) for 30 days and sign-in tokens for at most 30 days (see How long).',
      ],
    },
    {
      title: 'Why and on what basis',
      body: [
        'To keep your records: performance of a contract, Art. 6(1)(b) GDPR.',
        'The call log and tokens for security and to respect the services’ daily limits: legitimate interest, Art. 6(1)(f) GDPR.',
        'The app uses no advertising, analytics or tracking and does not sell data.',
      ],
    },
    {
      title: 'How long',
      body: [
        'Account and collection data until you delete the account. Call log 30 days.',
        'Sign-in until you close the browser, on the server at most 12 hours without use. If you tick Remember me when signing in, 30 days since last use. Signing out ends it at once.',
        'Before every update of the app to another version, the whole database is backed up on the server to the backups folder. The last 5 backups are kept, older ones are deleted. Data of a deleted account may remain in them until the backups rotate out.',
      ],
    },
    {
      title: 'Who receives it',
      body: [
        'The hosting provider the app runs on.',
        'Services you connect with your own key receive only the set numbers and barcodes you ask about, not your personal data. Eurostat receives nothing about you.',
        'Set pictures are loaded through the app’s server, so Rebrickable and Brickset do not see your IP address.',
      ],
    },
    {
      title: 'Your rights',
      body: [
        'Access and portability: in Settings → Account you download all your data and photos (ZIP).',
        'Rectification: change your data directly in the app.',
        'Erasure: in Settings → Account you delete the account with everything that belongs to it. It stays in the pre-update backups until they rotate out (see How long).',
        'Objection and restriction: write to the operator.',
        'Complaint: the Office for Personal Data Protection of the Slovak Republic, dataprotection.gov.sk.',
      ],
    },
  ]

  const sections = computed(() => (locale.value === 'sk' ? SK : EN))

  const storage = computed(() => [
    { name: 'lego_refresh', kind: 'cookie', purpose: t('privacy.storage.refresh'), lasts: t('privacy.storage.refreshLasts') },
    { name: 'lego-theme', kind: 'localStorage', purpose: t('privacy.storage.theme'), lasts: t('privacy.storage.untilCleared') },
    { name: 'lego-hide-prices', kind: 'localStorage', purpose: t('privacy.storage.hidePrices'), lasts: t('privacy.storage.untilCleared') },
    { name: 'moje-kocky.camera', kind: 'localStorage', purpose: t('privacy.storage.camera'), lasts: t('privacy.storage.untilCleared') },
    { name: 'moje-kocky.portfolio-range', kind: 'localStorage', purpose: t('privacy.storage.range'), lasts: t('privacy.storage.untilCleared') },
    { name: 'moje-kocky.cookie-note', kind: 'localStorage', purpose: t('privacy.storage.note'), lasts: t('privacy.storage.untilCleared') },
  ])
</script>

<template>
  <v-app>
    <v-main class="bg-background">
      <v-container class="privacy" style="max-width: 820px">
        <v-btn class="mb-2" prepend-icon="mdi-arrow-left" to="/prihlasenie" variant="text">
          {{ t('common.back') }}
        </v-btn>

        <h1 class="text-headline-large mb-1">{{ t('privacy.title') }}</h1>
        <div class="text-body-small text-medium-emphasis mb-4">{{ t('privacy.version', { version }) }}</div>

        <v-card border class="pa-4 mb-4" flat>
          <div class="text-body-large font-weight-medium mb-1">{{ t('privacy.operator') }}</div>

          <div v-if="operatorName || operatorEmail" class="text-body-large">
            {{ operatorName }}<span v-if="operatorName && operatorEmail">, </span>
            <a v-if="operatorEmail" :href="`mailto:${operatorEmail}`">{{ operatorEmail }}</a>
          </div>

          <v-alert v-else density="compact" type="warning" variant="tonal">{{ t('privacy.noOperator') }}</v-alert>
        </v-card>

        <section v-for="section in sections" :key="section.title" class="mb-5">
          <h2 class="text-title-large font-weight-medium mb-2">{{ section.title }}</h2>

          <ul class="ps-5">
            <li v-for="line in section.body" :key="line" class="text-body-large mb-1">{{ line }}</li>
          </ul>
        </section>

        <section class="mb-5">
          <h2 class="text-title-large font-weight-medium mb-2">{{ t('privacy.cookiesTitle') }}</h2>
          <p class="text-body-large mb-3">{{ t('privacy.cookiesIntro') }}</p>

          <v-table density="compact">
            <thead>
              <tr>
                <th>{{ t('privacy.storage.name') }}</th>
                <th>{{ t('privacy.storage.kind') }}</th>
                <th>{{ t('privacy.storage.purpose') }}</th>
                <th>{{ t('privacy.storage.lasts') }}</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="row in storage" :key="row.name">
                <td><code>{{ row.name }}</code></td>
                <td>{{ row.kind }}</td>
                <td>{{ row.purpose }}</td>
                <td>{{ row.lasts }}</td>
              </tr>
            </tbody>
          </v-table>
        </section>
      </v-container>
    </v-main>
  </v-app>
</template>
