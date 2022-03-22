<template>
  <div>
    <Header :hideHomepageBtn="true"></Header>
    <div class="container-fluid">
      <div class="row flex-nowrap">
        <div class="col">
          <div
            ref="slideProjectArea"
            id="slideProjectArea"
            class="my-4 mx-5"
            style="
              max-width: 45vw;
              max-height: 70vh;
              resize: vertical;
              overflow: auto;
            "
            :style="{
              width: Math.max(400, projectAreaWidth) + 'px',
            }"
          >
            <image-display
              :images="images"
              :slideHeight="Math.max(300, slideAreaHeight) + 'px'"
              :slideWidth="Math.max(400, projectAreaWidth) + 'px'"
            />
          </div>
          <div
            ref="textProjectArea"
            id="textProjectArea"
            class="card shadow-md my-4 mx-5 border border-3 border-dark"
            style="
              max-width: 45vw;
              max-height: 70vh;
              height: 500px;
              width: 800px;
              resize: both;
              overflow: auto;
            "
          >
            <div class="card-body overflow-auto">
              <p
                v-for="(sentence, i) in formatText(projected_text)"
                v-bind:key="i"
                :class="fsClass"
                class="text-start fw-bold"
              >
                <strong>{{ sentence }}</strong>
              </p>
            </div>
          </div>
          <nav class="mb-5 mx-4">
            <div class="container-fluid">
              <ul class="nav justify-content-start">
                <li class="nav-item mx-1 my-1">文字大小调节</li>
                <li class="nav-item mx-1">
                  <button
                    type="button"
                    class="btn btn-sm btn-primary col-sm-12"
                    :disabled="shrinkBtnDisabled"
                    v-on:click="onFontResizeClick(false)"
                  >
                    缩小
                  </button>
                </li>
                <li class="nav-item mx-1">
                  <button
                    type="button"
                    :disabled="enlargeBtnDisabled"
                    class="btn btn-sm btn-primary col-sm-12"
                    v-on:click="onFontResizeClick(true)"
                  >
                    放大
                  </button>
                </li>
                <li class="nav-item mx-1">
                  <button
                    type="button"
                    class="btn btn-sm btn-primary col-sm-12"
                    v-on:click="onFontSizeResetClick()"
                  >
                    重置
                  </button>
                </li>
              </ul>
            </div>
          </nav>
        </div>
        <div class="col">
          <div class="container mt-4">
            <nav
              class="my-2 navbar navbar-expand-lg navbar-light"
              :style="navbarStyling"
            >
              <div class="container-fluid">
                <ul class="navbar-nav d-flex" style="flex-wrap: wrap">
                  <li class="nav-item mx-1 my-1" style="max-width: 200px">
                    <select
                      class="form-select"
                      aria-label="Default select example"
                      id="question_type"
                      v-on:change="onQueryChange(true)"
                      v-model="queryParams['type']"
                    >
                      <option
                        v-for="q_type in ownerProfiles[owner].question_types"
                        v-bind:key="q_type.name"
                        :value="q_type.name"
                      >
                        {{ q_type.description }}
                      </option>
                    </select>
                  </li>
                  <li class="nav-item mx-1 my-1">
                    <select
                      class="form-select"
                      aria-label="Default select example"
                      id="reply_status"
                      v-on:change="onQueryChange(true)"
                      v-model="queryParams['reply_status']"
                    >
                      <option selected value="0">全部</option>
                      <option value="-1">未回复</option>
                      <option value="1">已回复</option>
                    </select>
                  </li>
                  <li class="nav-item mx-1 my-1">
                    <select
                      class="form-select"
                      aria-label="Default select example"
                      id="day_limit"
                      v-on:change="onQueryChange(true)"
                      v-model="queryParams['day_limit']"
                    >
                      <option value="1">1天内</option>
                      <option selected value="7">7天内</option>
                      <option value="30">30天内</option>
                      <option value="180">180天内</option>
                      <option value="365">1年内</option>
                    </select>
                  </li>
                  <li class="nav-item mx-1 my-1">
                    <select
                      class="form-select"
                      aria-label="Default select example"
                      id="order"
                      v-on:change="onQueryChange(false)"
                      v-model="queryParams['order_params_index']"
                    >
                      <option selected value="0">时间降序</option>
                      <option value="1">时间升序</option>
                      <option value="2">字数降序</option>
                      <option value="3">字数升序</option>
                    </select>
                  </li>
                  <li class="nav-item mx-1 my-1">
                    <select
                      class="form-select"
                      aria-label="Default select example"
                      id="order"
                      v-on:change="onQueryChange(true)"
                      v-model="queryParams['page_size']"
                    >
                      <option selected value="5">每页5条</option>
                      <option value="10">每页10条</option>
                      <option value="20">每页20条</option>
                      <option value="50">每页50条</option>
                    </select>
                  </li>
                  <li
                    class="nav-item mx-1 my-1 align-self-end"
                    style="height: 38px"
                  >
                    <pagination
                      v-model="queryParams['page']"
                      :records="total_count"
                      :per-page="queryParams['page_size']"
                      :options="{
                        chunk: 5,
                        format: false,
                        chunksNavigation: 'scroll',
                        edgeNavigation: true,
                        texts: {
                          count: '',
                          first: '<<',
                          last: '>>',
                        },
                      }"
                      @paginate="onQueryChange(false)"
                    />
                  </li>
                </ul>
              </div>
            </nav>
          </div>
          <div class="container overflow-auto" style="max-height: 80vh">
            <div class="card shadow-sm my-2" v-for="(q, i) in rows" :key="i">
              <div class="card-body">
                <div class="container">
                  <div class="row">
                    <div class="col-3">
                      <div class="list-group">
                        <li class="list-group-item">
                          字数： {{ q.word_count }}
                        </li>
                        <li class="list-group-item">
                          投稿时间： {{ formatTime(q.asked_at) }}
                        </li>
                        <li class="list-group-item">
                          回复时间： {{ formatTime(q.answered_at) }}
                        </li>
                        <li class="list-group-item">
                          <button
                            type="button"
                            class="btn btn-sm btn-warning m-1 col-sm-12"
                            v-on:click="
                              projectQuestion(
                                q.uuid,
                                q.text,
                                q.images,
                                q.answered_at
                              )
                            "
                          >
                            ← 投屏
                          </button>
                          <button
                            type="button"
                            class="btn d-none d-sm-block btn-sm btn-danger m-1 col-sm-12"
                            data-bs-toggle="modal"
                            data-bs-target="#confirmDeleteModal"
                          >
                            删除
                          </button>
                          <div
                            class="modal fade"
                            id="confirmDeleteModal"
                            tabindex="-1"
                            data-bs-backdrop="false"
                          >
                            <div class="modal-dialog modal-sm">
                              <div class="modal-content">
                                <div class="modal-header">
                                  <h5 class="modal-title">确认删除？</h5>
                                </div>
                                <div class="modal-body">
                                  <button
                                    type="button"
                                    class="btn btn-sm btn-danger mx-1"
                                    data-bs-dismiss="modal"
                                    :value="q.uuid"
                                    v-on:click="deleteQuestion"
                                  >
                                    确认
                                  </button>
                                  <button
                                    type="button"
                                    class="btn btn-sm btn-secondary mx-1"
                                    data-bs-dismiss="modal"
                                  >
                                    取消
                                  </button>
                                </div>
                              </div>
                            </div>
                          </div>
                        </li>
                      </div>
                    </div>
                    <div class="col-9">
                      <div class="card">
                        <div class="card-body">
                          <image-display
                            v-if="q.images && q.images.length > 0"
                            :images="q.images"
                            :slidesPerView="5"
                            :loop="false"
                            slideHeight="400px"
                            slideWidth="40vw"
                          />
                          <p
                            v-for="(sentence, i) in formatText(q.text)"
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
        </div>
      </div>
    </div>
  </div>
</template>
<script>
import Header from "./Header.vue";
import Pagination from "v-pagination-3";
import ImageDisplay from "./ImageDisplay.vue";
const storagePrefix = "ownerView_";
const orderDeriction = [
  { by: "asked_at", reversed: true },
  { by: "asked_at", reversed: false },
  { by: "word_count", reversed: true },
  { by: "word_count", reversed: false },
];

const fontSizes = ["fs-6", "fs-5", "fs-4", "fs-3", "fs-2", "fs-1"];
const defaultFontSizeIdx = 1;
var currentFontSizeIdx = defaultFontSizeIdx;

export default {
  // TODO: merge LiveView and OwnerView using setup() as they share the exactly the same component construction, only difference is the template
  name: "LiveView",
  components: {
    Pagination,
    Header,
    ImageDisplay,
  },
  props: {
    owner: String,
  },
  methods: {
    projectQuestion(uuid, text, images, answered_at) {
      this.projected_text = text;
      this.images = images;
      // automatically answer the question if it was not answered before
      let time = Date.parse(answered_at);
      const autoReply = `已于 ${new Date().toLocaleString("zh-CN", {
        hourCycle: "h23",
        timeZone: "Asia/Shanghai",
      })} 在直播中回应。
                请移步MeUmy录播组：https://space.bilibili.com/674622242
                根据回应时间寻找相应录播观看。
                再次感谢投稿！
                `.replace(/(\n)\s+/g, "$1");

      if (time === 0) {
        this.axios
          .put(
            "/api/owner/questions/" + uuid + "/answer",
            {
              uuid: uuid,
              answer: autoReply,
              answered_by: "auto",
            },
            {
              headers: { Authorization: `Bearer ${this.$route.query.token}` },
            }
          )
          .catch((err) => {
            console.log(err.response);
          });
      }
    },
    onQueryChange(resetPage, needRetry = false) {
      if (resetPage) this.queryParams["page"] = 1;
      this.axios
        .post(
          "/api/owner/questions",
          {
            owner: this.owner,
            type: this.queryParams["type"],
            order_params: {
              by: orderDeriction[this.queryParams["order_params_index"]].by,
              reversed:
                orderDeriction[this.queryParams["order_params_index"]].reversed,
            },
            reply_status: +this.queryParams["reply_status"],
            day_limit: +this.queryParams["day_limit"],
            page_size: +this.queryParams["page_size"],
            page: +this.queryParams["page"],
          },
          {
            headers: { Authorization: `Bearer ${this.$route.query.token}` },
          }
        )
        .then((resp) => {
          this.rows = resp.data.questions;
          this.total_count = resp.data.total;
        })
        .catch((err) => {
          console.log(err.response);
          if (err.response.status === 401 || err.response.status === 403) {
            alert(
              "神秘代码坏掉咯，要是你知道真正的管理员是谁的话就赶紧ping他要个新的吧！"
            );
            this.$router.push("/");
          } else {
            if (needRetry) {
              this.queryParams = {
                type: "normal",
                order_params_index: 0,
                reply_status: 0,
                day_limit: 7,
                page_size: 5,
                page: 1,
              };
              this.onQueryChange(false, false);
            } else {
              alert("提问箱好像坏掉了，直接ping管理员吧！");
              this.$router.push("/");
            }
          }
        });

      for (var key in this.queryParams) {
        if (this.queryParams.hasOwnProperty(key)) {
          localStorage.setItem(storagePrefix + key, this.queryParams[key]);
        }
      }
    },
    deleteQuestion(event) {
      this.axios
        .delete("api/owner/questions/" + event.target.value + "/delete", {
          headers: { Authorization: `Bearer ${this.$route.query.token}` },
        })
        .then(() => {
          this.onQueryChange();
        })
        .catch((err) => {
          console.log(err.response);
        });
    },
    openQuestion(event) {
      this.$router.push({
        name: "answer",
        query: {
          token: this.$route.query.token,
          uuid: event.target.value,
        },
      });
    },
    openLiveView() {
      this.$router.push({
        name: "live",
        query: {
          owner: this.owner,
          token: this.$route.query.token,
        },
      });
    },
    onFontResizeClick(enlarge) {
      if (enlarge) {
        if (currentFontSizeIdx < fontSizes.length - 1) {
          this.fsClass = fontSizes[++currentFontSizeIdx];
        }
      } else {
        if (currentFontSizeIdx > 0) {
          this.fsClass = fontSizes[--currentFontSizeIdx];
        }
      }
      this.shrinkBtnDisabled = currentFontSizeIdx <= 0;
      this.enlargeBtnDisabled = currentFontSizeIdx >= fontSizes.length - 1;
      console.log(
        currentFontSizeIdx,
        this.shrinkBtnDisabled,
        this.enlargeBtnDisabled
      );
    },
    onFontSizeResetClick() {
      currentFontSizeIdx = defaultFontSizeIdx;
      this.fsClass = fontSizes[currentFontSizeIdx];
      this.shrinkBtnDisabled = false;
      this.enlargeBtnDisabled = false;
    },
  },
  computed: {
    formatTime() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复";
        }
        return new Date(timeStr).toLocaleString("zh-CN", { hourCycle: "h23" });
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
    digest() {
      return (text) => {
        return text.substring(0, 30);
      };
    },
  },
  beforeMount() {
    this.navbarStyling = {
      "background-color": this.ownerProfiles[this.owner].colors.primary_color,
    };
    // try reading query params from local storage
    for (var key in this.queryParams) {
      if (this.queryParams.hasOwnProperty(key)) {
        let localVal = localStorage.getItem(storagePrefix + key);
        if (localVal && localVal !== "") {
          const parsedInt = parseInt(localVal);
          this.queryParams[key] = isNaN(parsedInt) ? localVal : parsedInt;
        }
      }
    }
    this.onQueryChange();
  },
  mounted() {
    const ob = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const cr = entry.contentRect;
        switch (entry.target.id) {
          case "slideProjectArea":
            this.slideAreaHeight = cr.height;
            break;
          case "textProjectArea":
            this.projectAreaWidth = cr.width;
        }
      }
    });

    ob.observe(this.$refs.slideProjectArea);
    ob.observe(this.$refs.textProjectArea);
  },
  data() {
    return {
      queryParams: {
        type: "normal",
        order_params_index: 0,
        reply_status: 0,
        day_limit: 7,
        page_size: 5,
        page: 1,
      },
      rows: [],
      total_count: 0,
      navbarStyling: {},
      images: [],
      projected_text: "",
      fsClass: fontSizes[defaultFontSizeIdx],
      enlargeBtnDisabled: false,
      shrinkBtnDisabled: false,
      slideAreaHeight: 300,
      projectAreaWidth: 400,
    };
  },
};
</script>

<style scoped>
.modal-dialog {
  top: 50vh;
  left: 25vw;
}
</style>
