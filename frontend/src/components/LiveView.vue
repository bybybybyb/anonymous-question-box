<template>
  <div>
    <Header></Header>
    <div class="container-fluid">
      <div class="row">
        <div class="col">
          <div
            class="card my-3 mx-5 border border-3 border-dark"
            style="width: 600px; height: 400px"
          >
            <div class="card-body overflow-auto">
              <h5
                v-for="(sentence, i) in formatText(projected_text)"
                v-bind:key="i"
                class="text-start"
              >
                {{ sentence }}
              </h5>
              <br />
            </div>
          </div>
          <div class="row">
            <p>
              本页面仍在测试中，目前以1920x1080分辨率100%缩放为基础制作，其他分辨率或缩放下可能无法正常工作。
            </p>
            <p>
              点击投屏将会复制投稿文本到左边空白中，并用当前时间自动回复投稿。
            </p>
          </div>
        </div>
        <div class="col">
          <div class="row">
            <div class="mx-5 my-3" style="width: 1070px">
              <nav
                class="
                  border-top border-start border-end border-1 border-dark
                  navbar navbar-expand-lg navbar-light
                "
                :style="navbarStyling"
              >
                <div class="container-fluid">
                  <ul class="navbar-nav">
                    <li class="nav-item mx-1 my-1">
                      <select
                        class="form-select"
                        aria-label="Default select example"
                        id="question_type"
                        v-on:change="onQueryChange"
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
                        v-on:change="onQueryChange"
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
                        v-on:change="onQueryChange"
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
                        v-on:change="onQueryChange"
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
                        v-on:change="onQueryChange"
                        v-model="queryParams['page_size']"
                      >
                        <option selected value="5">每页5条</option>
                        <option value="10">每页10条</option>
                        <option value="20">每页20条</option>
                        <option value="50">每页50条</option>
                      </select>
                    </li>
                    <li class="d-flex mx-1 my-1">
                      <pagination
                        v-model="queryParams['page']"
                        :records="total_count"
                        :per-page="queryParams['page_size']"
                        :options="{
                          chunk: 3,
                          format: false,
                          chunksNavigation: 'scroll',
                          edgeNavigation: true,
                          theme: 'bootstrap4',
                          texts: {
                            count: '',
                            first: '首页',
                            last: '末页',
                          },
                        }"
                        @paginate="onQueryChange"
                      />
                    </li>
                  </ul>
                </div>
              </nav>
              <div
                class="
                  card
                  border-start border-end border-bottom border-1 border-dark
                  overflow-auto
                "
                style="height: 745px; border-radius: 0rem"
              >
                <div class="card">
                  <div class="card m-2" v-for="(q, i) in rows" :key="i">
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
                                  class="
                                    btn btn-sm btn-outline-warning
                                    m-1
                                    col-sm-12
                                  "
                                  v-on:click="
                                    projectQuestion(
                                      q.uuid,
                                      q.text,
                                      q.answered_at
                                    )
                                  "
                                >
                                  ← 投屏
                                </button>
                                <button
                                  type="button"
                                  class="
                                    btn
                                    d-none d-sm-block
                                    btn-sm btn-outline-danger
                                    m-1
                                    col-sm-12
                                  "
                                  :value="q.uuid"
                                  v-on:click="deleteQuestion"
                                >
                                  删除
                                </button>
                              </li>
                            </div>
                          </div>
                          <div class="col-9">
                            <div class="card">
                              <div class="card-body">
                                <p
                                  v-for="(sentence, i) in formatText(q.text)"
                                  v-bind:key="i"
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
      </div>
    </div>
  </div>
</template>
<script>
import Header from "./Header.vue";
import Pagination from "v-pagination-3";
const storagePrefix = "ownerView_";
const orderDeriction = [
  { by: "asked_at", reversed: true },
  { by: "asked_at", reversed: false },
  { by: "word_count", reversed: true },
  { by: "word_count", reversed: false },
];

export default {
  // TODO: merge LiveView and OwnerView using setup() as they share the exactly the same component construction, only difference is the template
  name: "LiveView",
  components: {
    Pagination,
    Header,
  },
  props: {
    owner: String,
  },
  methods: {
    projectQuestion(uuid, text, answered_at) {
      this.projected_text = text;
      // automatically answer the question if it was not answered before
      let time = Date.parse(answered_at);
      authHeader = {
        headers: { Authorization: `Bearer ${this.$route.query.token}` },
      };
      if (time === 0) {
        this.axios
          .put(
            "/api/owner/questions/" + uuid + "/answer",
            {
              uuid: uuid,
              answer:
                "已在直播中回应，请根据回复时间寻找相应录播观看。再次感谢投稿！",
            },
            authHeader
          )
          .catch((err) => {
            console.log(err.response);
          });
      }
    },
    onQueryChange() {
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
  },
  computed: {
    formatTime() {
      return (timeStr) => {
        let time = Date.parse(timeStr);
        if (time === 0) {
          return "尚未回复";
        }
        return new Date(timeStr).toLocaleString();
      };
    },
    formatText() {
      return (text) => {
        if (text != null) {
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
      "background-color":
        this.ownerProfiles[this.owner].color_theme.primary_color,
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
      projected_text: "",
    };
  },
};
</script>