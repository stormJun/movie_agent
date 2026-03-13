/**
 * Reusable Page Layout Component
 * Solves the scroll-view height calculation issue
 *
 * Usage:
 *   <page-layout
 *     customScrollStyle="height: calc(100vh - {{navBarHeight}}px - {{inputBarHeight}}px);"
 *     bind:scrolltoupper="onLoadMore">
 *     <view slot="header"><!-- Nav bar, tabs --></view>
 *     <view>Your content here</view>
 *     <view slot="footer"><!-- Bottom bar --></view>
 *   </page-layout>
 */

Component({
  options: {
    multipleSlots: true,
    styleIsolation: 'apply-shared',
  },
  properties: {
    customScrollStyle: {
      type: String,
      value: '',
    },
    upperThreshold: {
      type: Number,
      value: 50,
    },
    lowerThreshold: {
      type: Number,
      value: 50,
    },
  },

  methods: {
    onScroll(e: WechatMiniprogram.ScrollViewScroll) {
      this.triggerEvent('scroll', e.detail);
    },

    onScrollToUpper(e: WechatMiniprogram.ScrollViewScroll) {
      this.triggerEvent('scrolltoupper', e.detail);
    },

    onScrollToLower(e: WechatMiniprogram.ScrollViewScroll) {
      this.triggerEvent('scrolltolower', e.detail);
    },

    /**
     * Scroll to bottom of content
     */
    scrollToBottom() {
      this.setData({
        scrollTop: 999999, // Large number ensures scroll to bottom
      });
    },

    /**
     * Scroll to specific position
     */
    scrollTo(top: number) {
      if (typeof top !== 'number' || Number.isNaN(top)) {
        return;
      }
      this.setData({
        scrollTop: top,
      });
    },
  },

  data: {
    scrollTop: 0,
  },
});
