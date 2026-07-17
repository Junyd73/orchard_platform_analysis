export type FarmDetail = {
  farm_cd: string
  farm_nm: string | null
  owner_nm: string | null
  address: string | null
  lat: number | null
  lon: number | null
  nx: number | null
  ny: number | null
  reg_dt: string | null
}

export type FarmSiteSummary = {
  site_id: string
  site_nm: string | null
  use_yn: string | null
}
