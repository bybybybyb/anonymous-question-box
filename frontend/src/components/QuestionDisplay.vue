<template>
  <div class="container">
    <div class="row">
      <div class="col-md-6 col-12">
        <div
          class="card shadow-lg my-3"
          style="background: rgba(255, 255, 255, 0.9)"
        >
          <div class="card-body">
            <div class="card">
              <h5 class="card-title mt-3">您的投稿</h5>
              <h6>投稿类型： {{ receiver }}</h6>
              <div
                class="card-body overflow-auto"
                :style="{
                  'max-height': questionCardMaxHeight + 'px',
                }"
              >
                <div class="container">
                  <div class="row">
                    <div class="col">
                      <swiper
                        v-if="images.length > 0"
                        ref="slide"
                        :style="{
                          '--swiper-navigation-color': '#000',
                          '--swiper-pagination-color': '#000',
                          'max-height': '500px',
                        }"
                        :modules="modules"
                        :spaceBetween="20"
                        :loop="true"
                        :slides-per-view="1"
                        :initialSlide="1"
                        navigation
                        :pagination="{ clickable: true }"
                      >
                        <swiper-slide
                          class="swiper-slide"
                          v-for="image in images"
                          v-bind:key="image.order"
                        >
                          <div
                            class="d-flex justify-content-center align-items-center"
                            style="height: 300px"
                          >
                            <a
                              data-bs-toggle="modal"
                              href="#fullscreenImg"
                              role="button"
                            >
                              <img
                                :src="image.url"
                                :alt="image.filename"
                                class="img-fluid img-thumbnail"
                                style="max-height: 300px"
                                v-show="false"
                                v-on:click="
                                  showFullscreenImg(image.url, image.filename)
                                "
                              />
                            </a>
                          </div>
                        </swiper-slide>
                      </swiper>
                    </div>
                  </div>
                  <div
                    class="row"
                    :style="{
                      'line-break': 'anywhere',
                    }"
                    ref="questionText"
                  >
                    <div class="col">
                      <p
                        v-for="(sentence, i) in formatText(question_text)"
                        v-bind:key="i"
                        class="lh-lg text-start"
                      >
                        {{ sentence }}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div class="card-footer" v-show="isLongText">
                <label
                  class="btn btn-outline-primary btn-sm"
                  v-on:click="textCardShowAllToggle"
                >
                  {{ showAllToggleText }}
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="col-md-6 col-12">
        <div
          class="card shadow-lg my-3"
          style="background: rgba(255, 255, 255, 0.9)"
        >
          <div class="card-body">
            <div class="card">
              <h5 class="card-title m-3">
                {{ generateAnswerTitle(answered_at) }}
              </h5>
              <div class="card-body overflow-auto" style="max-height: 500px">
                <div style="line-break: anywhere">
                  <p
                    v-for="(sentence, i) in formatText(answer_text)"
                    v-bind:key="i"
                    class="lh-lg text-start"
                  >
                    {{ sentence }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div
    class="modal fade"
    id="fullscreenImg"
    tabindex="-1"
    aria-hidden="true"
    v-if="images.length > 0"
  >
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
const defaultCardMaxHeight = 500;

import { Navigation, Pagination } from "swiper";
import { Swiper, SwiperSlide } from "swiper/vue";
import "swiper/css";
import "swiper/css/zoom";
import "swiper/css/navigation";
import "swiper/css/pagination";
import "swiper/css/scrollbar";

export default {
  name: "QuestionDisplay",
  components: {
    Swiper,
    SwiperSlide,
  },
  props: {
    receiver: String,
    question_text: String,
    asked_at: String,
    answer_text: String,
    answered_at: String,
    images: Array,
  },
  computed: {
    generateAnswerTitle() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复，请耐心等待。";
        }
        return "回信";
      };
    },
    formatText() {
      return (text) => {
        if (text !== null) {
          return text.split(/(?:\r\n|\r|\n)/g);
        }
        return [];
      };
    },
    textCardShowAllToggle() {
      return () => {
        this.questionCardMaxHeight =
          this.questionCardMaxHeight === defaultCardMaxHeight
            ? 10000
            : defaultCardMaxHeight;
        this.showAllToggleText =
          this.showAllToggleText === "展开显示" ? "收缩显示" : "展开显示";
      };
    },
  },
  mounted() {
    for (let img of this.images) {
      console.log(img);
    }
  },
  methods: {
    showFullscreenImg(url, alt) {
      this.fullscreenImgUrl = url;
      this.fullscreenImgAlt = alt;
    },
  },
  updated() {
    this.isLongText =
      this.$refs.questionText.clientHeight > defaultCardMaxHeight;
  },
  data() {
    return {
      questionCardMaxHeight: defaultCardMaxHeight,
      showAllToggleText: "展开显示",
      fullscreenImgUrl: "",
      fullscreenImgAlt: "",
      isLongText: false,
      modules: [Navigation, Pagination],
    };
  },
};
</script>
