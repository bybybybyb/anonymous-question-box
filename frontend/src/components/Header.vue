<template>
  <nav class="navbar navbar-expand-md navbar-dark bg-dark fixed-top">
    <div class="container-fluid">
      <span class="navbar-brand m-1 mb-0 h1">
        <img src="../assets/logo.png" alt="" height="32" />
        MeUmy草原提问箱
      </span>
      <ul class="navbar-nav mb-2 mb-lg-0">
        <li class="nav-item m-1">
          <button
            class="btn btn-sm btn-outline-warning"
            :class="{ 'd-none': hideHomepageBtn }"
            v-on:click="goHome"
          >
            返回主页
          </button>
        </li>
        <li class="nav-item m-1">
          <button
            class="btn btn-sm btn-outline-info"
            :class="{ 'd-none': hideBackBtn }"
            v-on:click="goBack"
          >
            返回上一页
          </button>
        </li>
        <li class="nav-item m-1">
          <button
            class="btn btn-sm btn-outline-light"
            v-on:click="contactAdmin"
          >
            联系管理员
          </button>
        </li>
      </ul>
    </div>
  </nav>
</template>

<script>
export default {
  name: "Header",
  props: {
    hideHomepageBtn: Boolean,
    hideBackBtn: Boolean,
  },
  methods: {
    goHome() {
      this.$router.push("homepage");
    },
    goBack() {
      this.$router.go(-1);
    },
    contactAdmin() {
      location.href = "https://space.bilibili.com/503";
    },
  },
  beforeCreate() {
    if (this.withHomepageBtn) {
    }
  },
};
</script>