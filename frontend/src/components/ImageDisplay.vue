<template>
  <div class="container-fluid">
    <div class="row">
      <div class="col">
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
          :navigation="images?.length > 1 && withNavigation"
          :loop="loop"
          :zoom="zoom ? { maxRatio: 5 } : false"
          :cssMode="disableMouseTouch"
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
              :class="zoom ? 'swiper-zoom-container' : ''"
              :style="{ height: slideHeight }"
            >
              <a v-if="!zoom" v-on:click="onModalToggleClicked($event)">
                <img
                  :src="image.url"
                  :alt="image.filename"
                  class="img-fluid"
                  :class="slidesPerView > 1 || !withNavigation ? 'pb-5' : 'p-5'"
                  :style="{ 'max-height': slideHeight }"
                  v-on:click="showFullscreenImg(image.url, image.filename)"
                />
              </a>
              <img
                v-else
                :src="image.url"
                :alt="image.filename"
                class="img-fluid"
                :class="slidesPerView > 1 || !withNavigation ? 'pb-5' : 'p-5'"
                :style="{ 'max-height': slideHeight }"
                v-on:click="showFullscreenImg(image.url, image.filename)"
              />
            </div>
          </swiper-slide>
        </swiper>
      </div>
    </div>
  </div>
  <div
    class="modal fade"
    :id="fullscreenImgModalId"
    tabindex="-1"
    v-if="images"
    data-bs-backdrop="false"
  >
    <div
      class="modal-dialog modal-dialog-centered modal-lg"
      :style="modalStyle"
    >
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
import { Navigation, Pagination, Zoom } from "swiper";
import { Swiper, SwiperSlide } from "swiper/vue";
import { Modal } from "bootstrap";
import "swiper/css";
import "swiper/css/zoom";
import "swiper/css/navigation";
import "swiper/css/pagination";
import "swiper/css/scrollbar";
import "swiper/css/zoom";

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
    withNavigation: {
      default: true,
      type: Boolean,
    },
    enableClickToFullscreen: {
      default: false,
      type: Boolean,
    },
    disableDoubleClick: {
      default: false,
      type: Boolean,
    },
    disableMouseTouch: {
      default: false,
      type: Boolean,
    },
    loop: {
      default: true,
      type: Boolean,
    },
    zoom: {
      default: false,
      type: Boolean,
    },
    images: {
      default: [],
      type: Array,
    },
    modalStyle: {
      default: {},
      type: Object,
    },
  },
  components: {
    Swiper,
    SwiperSlide,
  },
  methods: {
    onModalToggleClicked(event) {
      if (this.enableClickToFullscreen) {
        Modal.getOrCreateInstance(
          document.querySelector("#" + this.fullscreenImgModalId)
        ).show();
      }
    },
    showFullscreenImg(url, alt) {
      this.fullscreenImgUrl = url;
      this.fullscreenImgAlt = alt;
    },
  },
  beforeMount() {
    this.fullscreenImgModalId =
      "fullscreenImg" +
      Math.random()
        .toString(36)
        .replace(/[^a-z]+/g, "")
        .substr(0, 5);
  },
  data: {
    fullscreenImgUrl: "",
    fullscreenImgAlt: "",
    fullscreenImgModalId: "",
    modules: [Navigation, Pagination, Zoom],
  },
};
</script>
