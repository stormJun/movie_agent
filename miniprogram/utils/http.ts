export function httpGet<T = any>(url: string): Promise<T> {
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method: 'GET',
      header: { Accept: 'application/json' },
      success: res => {
        if (res.statusCode && res.statusCode >= 400) {
          const detail =
            typeof res.data === 'string'
              ? res.data.slice(0, 200)
              : res.data
              ? JSON.stringify(res.data).slice(0, 200)
              : '';
          reject(new Error(`HTTP ${res.statusCode} ${detail}`.trim()));
          return;
        }
        resolve(res.data as T);
      },
      fail: err => reject(err),
    });
  });
}

export function httpPost<T = any>(url: string, data: any): Promise<T> {
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method: 'POST',
      data,
      header: { 'Content-Type': 'application/json', Accept: 'application/json' },
      success: res => {
        if (res.statusCode && res.statusCode >= 400) {
          const detail =
            typeof res.data === 'string'
              ? res.data.slice(0, 200)
              : res.data
              ? JSON.stringify(res.data).slice(0, 200)
              : '';
          reject(new Error(`HTTP ${res.statusCode} ${detail}`.trim()));
          return;
        }
        resolve(res.data as T);
      },
      fail: err => reject(err),
    });
  });
}
