import http from './http'

export interface Health {
  app: string
  env: string
  db: { ok: boolean; error: string | null }
  storage: { root: string; writable: boolean; files: number; bytes: number }
  scheduler: boolean
}

export const getHealth = () => http.get<unknown, Health>('/health')

export interface Meta {
  app: string
  max_upload_mb: number
  timezone: string
  data_root: string
}

export const getMeta = () => http.get<unknown, Meta>('/meta')
