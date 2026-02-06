export interface AppInfo {
  productName: string
  webuiName: string
  releaseVersion: string
  buildVersion: string
}

export const appInfo: AppInfo = {
  productName: __APP_PRODUCT_NAME__,
  webuiName: __APP_WEBUI_NAME__,
  releaseVersion: __APP_RELEASE_VERSION__,
  buildVersion: __APP_BUILD_VERSION__,
}

