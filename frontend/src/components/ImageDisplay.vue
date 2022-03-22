<template>
  <swiper
    ref="slide"
    :style="{
      '--swiper-navigation-color': '#000',
      '--swiper-pagination-color': '#000',
      'max-height': slideHeight,
      'max-width': slideWidth,
    }"
    :modules="modules"
    :spaceBetween="10"
    :initialSlide="0"
    :navigation="images.length > 1"
    :loop="loop"
    :slides-per-view="slidesPerView"
    :pagination="{ clickable: true }"
    class="border-bottom"
  >
    <swiper-slide
      class="swiper-slide"
      v-for="image in images"
      v-bind:key="image.order"
    >
      <div
        class="d-flex justify-content-center align-items-center"
        :style="{ height: slideHeight }"
      >
        <a
          data-bs-toggle="modal"
          href="#fullscreenImg"
          role="button"
          :style="enableClickToFullscreen ? '' : 'pointer-events: none;'"
        >
          <img
            :src="image.url"
            :alt="image.filename"
            class="img-fluid"
            :class="slidesPerView > 1 ? '' : 'p-5'"
            :style="{ 'max-height': slideHeight }"
            v-on:click="showFullscreenImg(image.url, image.filename)"
          />
        </a>
      </div>
    </swiper-slide>
  </swiper>
  <div class="modal fade" id="fullscreenImg" tabindex="-1" v-if="images">
    <div class="modal-dialog modal-dialog-centered modal-lg">
      <div class="modal-content">
        <div class="modal-body">
          <img
            :src="fullscreenImgUrl"
            :alt="fullscreenImgAlt"
            class="img-fluid"
          />
        </div>
        <div class="modal-footer">
          <button
            type="button"
            class="btn btn-secondary"
            data-bs-dismiss="modal"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import { Navigation, Pagination } from "swiper";
import { Swiper, SwiperSlide } from "swiper/vue";
import "swiper/css";
import "swiper/css/zoom";
import "swiper/css/navigation";
import "swiper/css/pagination";
import "swiper/css/scrollbar";

export default {
  name: "ImageDisplay",
  props: {
    slideHeight: {
      default: "400px",
      type: String,
    },
    slideWidth: {
      default: "100%",
      type: String,
    },
    slidesPerView: {
      default: 1,
      type: Number,
    },
    enableClickToFullscreen: {
      default: false,
      type: Boolean,
    },
    loop: {
      default: true,
      type: Boolean,
    },
    images: {
      default: [],
      type: Array,
    },
  },
  components: {
    Swiper,
    SwiperSlide,
  },
  methods: {
    showFullscreenImg(url, alt) {
      this.fullscreenImgUrl = url;
      this.fullscreenImgAlt = alt;
    },
  },
  data: {
    fullscreenImgUrl: "",
    fullscreenImgAlt: "",
    modules: [Navigation, Pagination],
  },
};
</script>
