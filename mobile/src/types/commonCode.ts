/** GET /common-codes 응답 */
export type CommonCodeItem = {
  farm_cd: string
  code_cd: string
  code_nm: string
  parent_cd?: string | null
  use_yn?: string | null
}
