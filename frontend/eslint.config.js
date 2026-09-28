import vuetify from 'eslint-config-vuetify'

export default vuetify(
  { ts: true },
  {
    // Generované z OpenAPI príkazom `npm run gen:api`. Ručne sa needituje,
    // takže nemá zmysel ho ani kontrolovať.
    ignores: ['src/api/schema.d.ts'],
  },
)
