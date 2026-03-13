// app.ts
App<IAppOption>({
  globalData: {},
  onLaunch() {
    // MVP: 不依赖 wx.login / openid 流程，避免开发者工具在无权限 appid 下触发 ticket/config 拉取。
  },
})
