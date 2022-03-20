<template>
  <div>
    <Header :hideBackBtn="true"></Header>
    <div class="container">
      <div class="card" style="background: rgba(255, 255, 255, 0.9)">
        <div class="card-header">
          <nav
            class="navbar navbar-expand-lg navbar-light justify-content-between border border-1"
            :style="navbarStyling"
          >
            <div class="container-fluid">
              <ul class="navbar-nav">
                <li class="nav-item m-1">
                  <select
                    class="form-select"
                    aria-label="question type select"
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
                <li class="nav-item m-1">
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
                    <option value="2">已手动回复</option>
                  </select>
                </li>
                <li class="nav-item m-1">
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
                <li class="nav-item m-1">
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
                <li class="nav-item m-1">
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
                <form class="form-inline">
                  <button
                    type="button"
                    class="btn d-none d-sm-block btn-primary m-1"
                    v-on:click="openLiveView"
                  >
                    直播模式
                  </button>
                </form>
              </ul>
            </div>
          </nav>
        </div>
        <div class="card shadow-lg m-3" v-for="(q, i) in rows" :key="i">
          <div class="card-header">
            <div class="row">
              <div class="col-12 col-md-2 d-none d-sm-table-cell">
                字数： {{ q.word_count }}
              </div>
              <div class="col-12 col-md-5">
                投稿时间： {{ formatTime(q.asked_at) }}
              </div>
              <div class="col-12 col-md-5" :style="q.visit_status_color">
                回复时间： {{ formatTime(q.answered_at) }}
              </div>
            </div>
          </div>
          <div class="card-body">
            <div class="row">
              <div class="col-12 col-sm-10">
                <p class="card-text">
                  {{ digest(q.text) }}
                </p>
              </div>
              <div class="col-12 col-sm-2">
                <a
                  class="btn btn-sm btn-outline-danger m-1"
                  v-on:click="deleteQuestion(q.uuid)"
                >
                  删除
                </a>
                <a
                  class="btn btn-sm btn-outline-info m-1"
                  v-on:click="openQuestion(q.uuid)"
                  data-bs-toggle="modal"
                  data-bs-target="#answerModal"
                >
                  打开
                </a>
              </div>
            </div>
          </div>
        </div>
        <div class="container">
          <div class="row">
            <div class="col-12 p-3">
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
                    count:
                      '显示第 {from} 到 {to} 条，共 {count} 条|共 {count} 条|共 1 条',
                    first: '首页',
                    last: '末页',
                  },
                }"
                @paginate="onQueryChange(false)"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="modal" tabindex="-1" id="answerModal">
      <div class="modal-dialog modal-lg modal-dialog-scrollable">
        <div class="modal-content">
          <div class="modal-header">
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <answer-view :changeQuestion="uuid"></answer-view>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Header from "./Header.vue";
import Pagination from "v-pagination-3";
import AnswerView from "./AnswerView.vue";
const storagePrefix = "ownerView_";
const storagePrefixAnswerView = "AnswerView_draft_";
const orderDeriction = [
  { by: "asked_at", reversed: true },
  { by: "asked_at", reversed: false },
  { by: "word_count", reversed: true },
  { by: "word_count", reversed: false },
];

export default {
  // TODO: merge LiveView and OwnerView using setup() as they share the exactly the same component construction, only difference is the template
  name: "OwnerView",
  components: {
    Pagination,
    Header,
    AnswerView,
  },
  props: {
    owner: String,
  },
  methods: {
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
          for (let row of this.rows) {
            if (row.answered_by === "manual") {
              if (row.visit_count > 0) {
                row.visit_status_color = {
                  color: "green",
                };
              } else {
                row.visit_status_color = {
                  color: "lightskyblue",
                };
              }
            } else {
              row.visit_status_color = {
                color: "black",
              };
            }
          }
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
    deleteQuestion(uuid) {
      this.axios
        .delete("api/owner/questions/" + uuid + "/delete", {
          headers: { Authorization: `Bearer ${this.$route.query.token}` },
        })
        .then(() => {
          localStorage.removeItem(storagePrefixAnswerView + this.uuid);
          this.onQueryChange();
        })
        .catch((err) => {
          console.log(err.response);
        });
    },
    openQuestion(uuid) {
      this.uuid = uuid;
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
    visitStatusColor() {
      return;
    },
  },
  computed: {
    answerPopup() {
      var cc = Vue.extend(AnswerView);
      var ans = new cc(this.token, this.uuid);
      return {
        ans,
      };
    },
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
        if (text != null) {
          return text.split(/(?:\r\n|\r|\n)/g);
        }
        return [];
      };
    },
    digest() {
      return (text) => {
        let digested = text.substring(0, 50);
        if (digested.length < text.length) digested += "......";
        return digested;
      };
    },
  },
  beforeMount() {
    // change back the body background
    document.body.classList.remove("bg-light");
    document.body.classList.add(
      "body-background-texture-" + this.owner + "-light"
    );
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
    this.onQueryChange(true, true);
  },
  beforeUnmount() {
    // change back the body background
    document.body.classList.remove(
      "body-background-texture-" + this.owner + "-light"
    );
    document.body.classList.add("bg-light");
  },
  data() {
    return {
      queryParams: {
        type: "normal",
        order_params_index: 0,
        reply_status: 0,
        day_limit: 30,
        page_size: 5,
        page: 1,
      },
      rows: [],
      total_count: 0,
      navbarStyling: {},
      projected_text: "",
      uuid: "",
    };
  },
};
</script>
