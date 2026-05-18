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
              <ul class="navbar-nav owner-filter-grid">
                <li class="nav-item m-1 owner-filter-control">
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
                <li class="nav-item m-1 owner-filter-control">
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
                <li class="nav-item m-1 owner-filter-control">
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
                <li class="nav-item m-1 owner-filter-control" v-if="locationOptions.length > 0">
                  <select
                    class="form-select"
                    aria-label="location select"
                    id="location_addr"
                    v-on:change="onQueryChange(true)"
                    v-model="queryParams['ip_addr']"
                  >
                    <option value="">全部地区</option>
                    <option
                      v-for="option in locationOptions"
                      v-bind:key="option.addr"
                      :value="option.addr"
                    >
                      {{ option.label }}（{{ option.count }}）
                    </option>
                  </select>
                </li>
                <li class="nav-item m-1 owner-filter-control">
                  <select
                    class="form-select"
                    aria-label="Default select example"
                    id="order"
                    v-on:change="onQueryChange(false)"
                    v-model="queryParams['order_params_index']"
                  >
                    <option selected value="0">时间从新到旧</option>
                    <option value="1">时间从旧到新</option>
                    <option value="2">字数从多到少</option>
                    <option value="3">字数从少到多</option>
                  </select>
                </li>
                <li class="nav-item m-1 owner-filter-control">
                  <select
                    class="form-select"
                    aria-label="Default select example"
                    id="page_size"
                    v-on:change="onQueryChange(true)"
                    v-model="queryParams['page_size']"
                  >
                    <option selected value="5">每页5条</option>
                    <option value="10">每页10条</option>
                    <option value="20">每页20条</option>
                    <option value="50">每页50条</option>
                  </select>
                </li>
                <li class="nav-item m-1 owner-filter-control owner-filter-wide">
                  <div class="form-check-inline">
                    <input
                      type="checkbox"
                      class="btn-check form-check-input"
                      autocomplete="off"
                      id="markedOnlyCheckbox"
                      v-model="markedOnly"
                      @change="onQueryChange(true)"
                    />
                    <label
                      class="btn btn-warning form-check-label"
                      for="markedOnlyCheckbox"
                    >
                      {{ markedOnly ? "显示全部" : "只显示已标记" }}
                    </label>
                  </div>
                </li>
                <form class="form-inline owner-filter-actions">
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
          <div class="btn-group mt-3" role="group" aria-label="moderation list mode">
            <button
              type="button"
              class="btn btn-sm"
              :class="{
                'btn-primary': activeListMode === 'normal',
                'btn-outline-primary': activeListMode !== 'normal',
              }"
              v-on:click="switchListMode('normal')"
            >
              全部投稿
            </button>
            <button
              type="button"
              class="btn btn-sm"
              :class="{
                'btn-danger': activeListMode === 'review',
                'btn-outline-danger': activeListMode !== 'review',
              }"
              v-on:click="switchListMode('review')"
            >
              审核队列
              <span class="badge rounded-pill bg-white text-danger border border-danger ms-1">
                {{ moderationCounts.blocked }}
              </span>
            </button>
          </div>
        </div>
        <div v-if="activeListMode === 'normal'">
          <div class="card shadow-lg m-3" v-for="q in rows" :key="q.uuid">
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
                <div class="col-12 mt-1 small text-muted" v-if="q.ip">
                  IP：{{ q.ip }}
                  <span v-if="q.ip_addr || q.ip_isp"
                    >（{{ [q.ip_addr, q.ip_isp].filter(Boolean).join(" / ") }}）</span
                  >
                </div>
              </div>
            </div>
            <div class="card-body">
              <div class="row">
                <div class="col-12 col-sm-9">
                  <p class="card-text">
                    {{ digest(q.text) }}
                  </p>
                </div>
                <div class="col-12 col-sm-3">
                  <a
                    class="btn btn-sm m-1"
                    :class="{
                      'btn-warning': q.marked,
                      'btn-outline-warning': !q.marked,
                    }"
                    v-on:click="markQuestion(q)"
                  >
                    {{ q.marked ? "取消标记" : "标记" }}
                  </a>
                  <a
                    class="btn btn-sm btn-outline-danger m-1"
                    v-on:click="prepareDeleteQuestion(q.uuid)"
                    data-bs-toggle="modal"
                    data-bs-target="#confirmDeleteModal"
                  >
                    删除
                  </a>
                  <a
                    class="btn btn-sm btn-outline-info m-1"
                    v-on:click="openAnswerQuestion(q.uuid)"
                    data-bs-toggle="modal"
                    data-bs-target="#answerModal"
                  >
                    详情
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="activeListMode === 'review'">
          <div class="card shadow-lg m-3" v-if="rows.length === 0">
            <div class="card-body text-center text-muted py-4">暂无待审核投稿</div>
          </div>
          <div
            class="card shadow-lg m-3"
            v-for="q in rows"
            :key="q.uuid"
            :data-review-uuid="q.uuid"
          >
            <div class="card-header">
              <div class="row align-items-center">
                <div class="col-12">
                  投稿时间： {{ formatTime(q.asked_at) }}
                </div>
                <div class="col-12 mt-1 small text-muted" v-if="q.ip">
                  IP：{{ q.ip }}
                  <span v-if="q.ip_addr || q.ip_isp"
                    >（{{ [q.ip_addr, q.ip_isp].filter(Boolean).join(" / ") }}）</span
                  >
                </div>
              </div>
            </div>
            <div class="card-body">
              <div class="row">
                <div class="col-12 col-sm-9">
                  <p class="card-text fw-semibold mb-0">
                    {{ moderationReviewSummary(q) }}
                  </p>
                </div>
                <div class="col-12 col-sm-3 mt-2 mt-sm-0">
                  <button
                    type="button"
                    class="btn btn-sm btn-outline-success m-1"
                    v-on:click="approveQuestion(q)"
                  >
                    批准
                  </button>
                  <button
                    type="button"
                    class="btn btn-sm btn-outline-danger m-1"
                    v-on:click="prepareDeleteQuestion(q.uuid)"
                    data-bs-toggle="modal"
                    data-bs-target="#confirmDeleteModal"
                  >
                    删除
                  </button>
                  <button
                    type="button"
                    class="btn btn-sm btn-outline-info m-1"
                    v-on:click="openAnswerQuestion(q.uuid)"
                    data-bs-toggle="modal"
                    data-bs-target="#answerModal"
                  >
                    详情
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="container">
          <div class="row">
            <div class="col-12 p-3 owner-pagination">
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

    <div class="modal fade" id="confirmDeleteModal" tabindex="-1">
      <div class="modal-dialog modal-dialog-centered modal-sm">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">确认删除？</h5>
          </div>
          <div class="modal-body">
            <button
              type="button"
              class="btn btn-sm btn-danger mx-1"
              data-bs-dismiss="modal"
              v-on:click="deleteQuestion()"
            >
              确认
            </button>
            <button
              type="button"
              class="btn btn-sm btn-secondary mx-1"
              data-bs-dismiss="modal"
              v-on:click="closeQuestion()"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal fade" tabindex="-1" id="answerModal">
      <div
        class="modal-dialog modal-lg modal-dialog-scrollable modal-fullscreen-md-down"
      >
        <div class="modal-content">
          <div class="modal-header">
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
            <button
              type="button"
              id="btnOpenImgModal"
              ref="btnOpenImgModal"
              v-show="false"
              data-bs-toggle="modal"
              data-bs-target="imgModal"
            >
              switch
            </button>
          </div>
          <div class="modal-body">
            <answer-view
              :changeQuestion="uuid"
              v-on:fullscreenImg="switchToImgModal($event)"
            ></answer-view>
          </div>
        </div>
      </div>
    </div>
    <div class="modal fade" tabindex="-1" id="imgModal" ref="imgModal">
      <div class="modal-dialog modal-dialog-scrollable modal-lg">
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
            <div class="row">
              <image-display
                :images="images"
                :withNavigation="false"
                :withModal="false"
                :autoHeight="true"
                slideHeight="100%"
              />
            </div>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-sm btn-outline-info"
              data-bs-toggle="modal"
              data-bs-target="#answerModal"
            >
              返回投稿
            </button>
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
import ImageDisplay from "./ImageDisplay.vue";
import { Modal } from "bootstrap";
const storagePrefix = "ownerView_";
const storagePrefixAnswerView = "AnswerView_draft_";
// Location options are per owner/type and can be empty for historical rows, so never persist them across boxes.
const transientQueryParamKeys = new Set(["ip_addr"]);
const orderDirection = [
  { by: "asked_at", reversed: true },
  { by: "asked_at", reversed: false },
  { by: "word_count", reversed: true },
  { by: "word_count", reversed: false },
];
const queryDebounceMs = 200;
const listModes = {
  normal: {
    moderationStatus: "normal",
  },
  review: {
    moderationStatus: "blocked",
  },
};
const defaultListMode = "normal";

export default {
  name: "OwnerView",
  components: {
    Pagination,
    Header,
    AnswerView,
    ImageDisplay,
  },
  props: {
    owner: String,
  },
  methods: {
    switchToImgModal(images) {
      this.images = images;
      Modal.getOrCreateInstance(document.querySelector("#answerModal")).hide();
      Modal.getOrCreateInstance(document.querySelector("#imgModal")).show();
    },
    onQueryChange(resetPage, needRetry = false, debounce = true) {
      if (debounce) {
        clearTimeout(this.queryDebounceTimer);
        this.queryDebounceTimer = setTimeout(
          () => this.onQueryChange(resetPage, needRetry, false),
          queryDebounceMs
        );
        return;
      }
      clearTimeout(this.queryDebounceTimer);
      if (resetPage) this.queryParams["page"] = 1;
      this.axios
        .post(
          "/api/owner/questions",
          this.buildListRequest(),
          {
            headers: { Authorization: `Bearer ${this.$route.query.token}` },
          }
        )
        .then((resp) => this.applyListResponse(resp))
        .catch((err) => {
          console.log(err.response);
          if (err.response.status === 401 || err.response.status === 403) {
            alert(
              "神秘代码坏掉咯，要是你知道真正的管理员是谁的话就赶紧ping他要个新的吧！"
            );
            this.$router.push("/");
          } else {
            if (needRetry) {
              this.queryParams = this.defaultQueryParams();
              this.onQueryChange(false, false, false);
            } else {
              alert(this.legacyErrorMessage(err, "提问箱好像坏掉了，直接ping管理员吧！"));
              this.$router.push("/");
            }
          }
        });

      this.persistQueryParams();
    },
    buildListRequest() {
      const orderParams = orderDirection[this.queryParams["order_params_index"]];
      return {
        owner: this.owner,
        type: this.queryParams["type"],
        moderation_status: this.currentListMode.moderationStatus,
        order_params: {
          by: orderParams.by,
          reversed: orderParams.reversed,
        },
        marked: this.markedOnly,
        reply_status: +this.queryParams["reply_status"],
        day_limit: +this.queryParams["day_limit"],
        ip_addr: this.queryParams["ip_addr"],
        page_size: +this.queryParams["page_size"],
        page: +this.queryParams["page"],
      };
    },
    applyListResponse(resp) {
      const rows = resp.data.questions || [];
      const visibleRows =
        this.activeListMode === "review"
          ? rows.filter((row) => row.moderation?.source !== "keyword")
          : rows;
      this.total_count = resp.data.total;
      this.locationOptions = resp.data.location_options || [];
      this.moderationCounts = {
        blocked: resp.data.moderation_counts?.blocked || 0,
      };
      this.rows = visibleRows.map((row) => this.withVisitStatusColor(row));
    },
    withVisitStatusColor(row) {
      if (row.answered_by === "manual") {
        return {
          ...row,
          visit_status_color: {
            color: row.visit_count > 0 ? "green" : "lightskyblue",
          },
        };
      }
      return {
        ...row,
        visit_status_color: {
          color: "black",
        },
      };
    },
    persistQueryParams() {
      for (var key in this.queryParams) {
        if (this.queryParams.hasOwnProperty(key)) {
          if (transientQueryParamKeys.has(key)) {
            localStorage.removeItem(storagePrefix + key);
            continue;
          }
          localStorage.setItem(storagePrefix + key, this.queryParams[key]);
        }
      }
    },
    defaultQueryParams() {
      return {
        type: "normal",
        order_params_index: 0,
        reply_status: 0,
        day_limit: 7,
        ip_addr: "",
        page_size: 5,
        page: 1,
      };
    },
    switchListMode(mode) {
      if (!listModes[mode] || this.activeListMode === mode) return;
      this.activeListMode = mode;
      this.onQueryChange(true, false, false);
    },
    markQuestion(q) {
      this.axios
        .put(
          "/api/owner/questions/" + q.uuid + "/mark",
          {
            owner: q.owner,
            type: q.type,
            mark: !q.marked,
          },
          {
            headers: { Authorization: `Bearer ${this.$route.query.token}` },
          }
        )
        .then(() => {
          this.onQueryChange(true, false, false);
        })
        .catch((err) => {
          console.log(err.response);
          if (err.response.status === 401 || err.response.status === 403) {
            alert(
              "神秘代码坏掉咯，要是你知道真正的管理员是谁的话就赶紧ping他要个新的吧！"
            );
            this.$router.push("/");
          } else if (err.response.status === 404) {
          } else {
            alert("提问箱好像坏掉了，直接ping管理员吧！");
            this.$router.push("/");
          }
        });
    },
    approveQuestion(q) {
      this.axios
        .put("/api/owner/questions/" + q.uuid + "/moderation/approve", null, {
          headers: { Authorization: `Bearer ${this.$route.query.token}` },
        })
        .then(() => {
          this.onQueryChange(false, false, false);
        })
        .catch((err) => {
          console.log(err.response);
          if (err.response.status === 401 || err.response.status === 403) {
            alert(
              "神秘代码坏掉咯，要是你知道真正的管理员是谁的话就赶紧ping他要个新的吧！"
            );
            this.$router.push("/");
          } else {
            alert(this.legacyErrorMessage(err, "提问箱提问审核好像坏掉了，直接ping管理员吧！"));
          }
        });
    },
    deleteQuestion() {
      const toDelete =
        this.pendingDeleteUuid || localStorage.getItem(storagePrefix + "opened_question");
      this.axios
        .delete("/api/owner/questions/" + toDelete + "/delete", {
          headers: { Authorization: `Bearer ${this.$route.query.token}` },
        })
        .then(() => {
          localStorage.removeItem(storagePrefixAnswerView + toDelete);
          if (toDelete === this.uuid) this.uuid = "";
          this.closeQuestion();
          this.onQueryChange(false, false, false);
        })
        .catch((err) => {
          console.log(err.response);
        });
    },
    openAnswerQuestion(uuid) {
      this.uuid = "";
      this.$nextTick(() => {
        this.uuid = uuid;
        localStorage.setItem(storagePrefix + "opened_question", uuid);
      });
    },
    prepareDeleteQuestion(uuid) {
      this.pendingDeleteUuid = uuid;
      localStorage.setItem(storagePrefix + "opened_question", uuid);
    },
    closeQuestion() {
      this.pendingDeleteUuid = "";
      localStorage.removeItem(storagePrefix + "opened_question");
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
    legacyErrorMessage(err, fallback) {
      return err?.response?.data?.error || fallback;
    },
    moderationReviewSummary(q) {
      const moderation = q.moderation || {};
      if (this.isChineseText(moderation.short_reason)) return moderation.short_reason;
      return this.moderationChineseFallback(moderation);
    },
    moderationChineseFallback(moderation) {
      const categoryLabels = {
        privacy: "疑似隐私风险",
        doxxing: "疑似人肉或隐私泄露",
        identity_speculation: "疑似身份猜测",
        harassment: "疑似骚扰或攻击内容",
        threats: "疑似威胁内容",
        spam: "疑似垃圾内容",
        explicit_sexual_content: "疑似露骨内容",
        fan_drama: "疑似粉圈争议引导",
        other: "需要人工复核",
        safe: "未发现明显风险",
      };
      const reasonLabels = {
        model_reject: "需要人工复核",
        policy_block: "触发审核策略",
        manual: "人工审核",
      };
      return (
        categoryLabels[moderation.category] ||
        reasonLabels[moderation.reason] ||
        "需要人工复核"
      );
    },
    isChineseText(text) {
      return /[\u3400-\u9fff]/.test(text || "");
    },
  },
  computed: {
    currentListMode() {
      return listModes[this.activeListMode] || listModes[defaultListMode];
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
        if (transientQueryParamKeys.has(key)) {
          localStorage.removeItem(storagePrefix + key);
          continue;
        }
        let localVal = localStorage.getItem(storagePrefix + key);
        if (localVal && localVal !== "") {
          const parsedInt = parseInt(localVal);
          this.queryParams[key] = isNaN(parsedInt) ? localVal : parsedInt;
        }
      }
    }
    this.onQueryChange(true, true, false);
  },
  beforeUnmount() {
    clearTimeout(this.queryDebounceTimer);
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
        ip_addr: "",
        page_size: 5,
        page: 1,
      },
      rows: [],
      images: [],
      locationOptions: [],
      total_count: 0,
      navbarStyling: {},
      projected_text: "",
      uuid: "",
      pendingDeleteUuid: "",
      markedOnly: false,
      activeListMode: defaultListMode,
      moderationCounts: {
        blocked: 0,
      },
      queryDebounceTimer: null,
    };
  },
};
</script>

<style scoped>
@media (max-width: 575.98px) {
  .owner-filter-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.5rem;
    width: 100%;
  }

  .owner-filter-control {
    margin: 0 !important;
    min-width: 0;
  }

  .owner-filter-control .form-select,
  .owner-filter-control .btn {
    width: 100%;
  }

  .owner-filter-wide,
  .owner-filter-actions {
    grid-column: 1 / -1;
  }

  .owner-filter-wide {
    display: flex;
    justify-content: center;
  }

  .owner-filter-wide .btn {
    width: auto;
    min-width: 9rem;
  }
}

.owner-pagination {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.owner-pagination :deep(.VuePagination__pagination) {
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.owner-pagination :deep(.VuePagination__count) {
  margin-bottom: 0;
  text-align: center;
}
</style>
