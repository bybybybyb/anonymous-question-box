<template>
  <Header></Header>
  <div class="container">
    <div class="card my-3">
      <div class="card-body border border-2">
        <nav
          class="
            navbar navbar-expand-lg navbar-light
            justify-content-between
            border-top border-start border-end border-1 border-dark
          "
          :style="navbarStyling"
        >
          <div class="container-fluid">
            <ul class="navbar-nav">
              <li class="nav-item mx-1 my-1">
                <select
                  class="form-select form-select-sm"
                  aria-label="Default select example"
                  id="question_type"
                  v-on:change="onQueryChange"
                  v-model="type"
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
                  class="form-select form-select-sm"
                  aria-label="Default select example"
                  id="reply_status"
                  v-on:change="onQueryChange"
                  v-model="reply_status"
                >
                  <option selected value="0">全部</option>
                  <option value="-1">未回复</option>
                  <option value="1">已回复</option>
                </select>
              </li>
              <li class="nav-item mx-1 my-1">
                <select
                  class="form-select form-select-sm"
                  aria-label="Default select example"
                  id="day_limit"
                  v-on:change="onQueryChange"
                  v-model="day_limit"
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
                  class="form-select form-select-sm"
                  aria-label="Default select example"
                  id="order"
                  v-on:change="onQueryChange"
                  v-model="order_param_index"
                >
                  <option selected value="0">时间降序</option>
                  <option value="1">时间升序</option>
                  <option value="2">字数降序</option>
                  <option value="3">字数升序</option>
                </select>
              </li>
              <li class="nav-item mx-1 my-1">
                <select
                  class="form-select form-select-sm"
                  aria-label="Default select example"
                  id="order"
                  v-on:change="onQueryChange"
                  v-model="page_size"
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
                  class="
                    btn btn-sm
                    d-none d-sm-block
                    btn-sm btn-primary
                    mx-1
                    my-1
                  "
                  v-on:click="openLiveView"
                >
                  直播模式
                </button>
              </form>
            </ul>
          </div>
        </nav>
        <div class="table-responsive border border-1 border-dark">
          <table class="table table-striped">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col" class="d-none d-sm-table-cell">预览</th>
                <th scope="col">字数</th>
                <th scope="col">投稿时间</th>
                <th scope="col">回复时间</th>
                <th scope="col">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(q, i) in rows" :key="i">
                <td scope="row">{{ i + 1 }}</td>
                <td class="d-none d-sm-table-cell">{{ digest(q.text) }}</td>
                <td>{{ q.word_count }}</td>
                <td>{{ formatTime(q.asked_at) }}</td>
                <td>{{ formatTime(q.answered_at) }}</td>
                <td>
                  <button
                    type="button"
                    class="btn btn-sm btn-outline-info my-1 mx-1 col-sm-12"
                    :value="q.uuid"
                    v-on:click="openQuestion"
                  >
                    打开
                  </button>
                  <button
                    type="button"
                    class="
                      btn
                      d-none d-sm-block
                      btn-sm btn-outline-danger
                      my-1
                      mx-1
                      col-sm-12
                    "
                    :value="q.uuid"
                    v-on:click="deleteQuestion"
                  >
                    删除
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="container">
          <div class="row">
            <div class="col-12 p-3">
              <pagination
                v-model="page"
                :records="total_count"
                :per-page="page_size"
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
                @paginate="onQueryChange"
              />
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
let orderDeriction = [
  { by: "asked_at", reversed: true },
  { by: "asked_at", reversed: false },
  { by: "word_count", reversed: true },
  { by: "word_count", reversed: false },
];

export default {
  name: "OwnerView",
  components: {
    Pagination,
    Header,
  },
  props: {
    owner: String,
  },
  methods: {
    onQueryChange() {
      this.axios
        .post(
          "/api/owner/questions",
          {
            owner: this.owner,
            type: this.type,
            order_params: {
              by: orderDeriction[this.order_param_index].by,
              reversed: orderDeriction[this.order_param_index].reversed,
            },
            reply_status: +this.reply_status,
            day_limit: +this.day_limit,
            page_size: +this.page_size,
            page: +this.page,
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
          console.log(err);
        });
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
          type: this.type,
          order_param_index: this.order_param_index,
          day_limit: this.day_limit,
          reply_status: this.reply_status,
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
    if (this.$route.query.type != null) this.type = this.$route.query.type;
    if (this.$route.query.order_param_index != null)
      this.order_param_index = this.$route.query.order_param_index;
    if (this.$route.query.reply_status != null)
      this.reply_status = this.$route.query.reply_status;
    if (this.$route.query.day_limit != null)
      this.day_limit = this.$route.query.day_limit;
    if (this.$route.query.page != null) this.page = this.$route.query.page;
    if (this.$route.query.page_size != null)
      this.page_size = this.$route.query.page_size;
    this.onQueryChange();
  },
  data() {
    return {
      rows: [],
      type: "normal",
      order_param_index: 0,
      day_limit: 7,
      reply_status: 0,
      total_count: 0,
      page_size: 5,
      page: 1,
      navbarStyling: {},
    };
  },
};
</script>