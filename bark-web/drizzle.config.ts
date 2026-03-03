import { defineConfig } from 'drizzle-kit';

export default defineConfig({
    out: './src/db/drizzle',
    schema: './src/db/drizzle/schema.ts',
    dialect: 'postgresql',
    dbCredentials: {
        url: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/barkbot',
    },
    verbose: true,
    strict: true,
});
