// NOT CURRENTLY USED — no route or page imports `db` from this module. Job/
// event state lives in the server's disk-backed JobStore (server/app/store.py),
// not Postgres. This client + prisma/schema.prisma are scaffolded ahead of a
// future multi-tenant/OAuth milestone (see the schema's header comment) —
// intentional, not abandoned, but nothing is wired to it yet. If you're
// looking for where job data actually persists, start at server/app/store.py.
import { PrismaClient } from "./generated/prisma";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const db =
  globalForPrisma.prisma ??
  new PrismaClient({ log: process.env.NODE_ENV === "development" ? ["error"] : [] });

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = db;
