<template>
  <nav class="navbar navbar-expand-md navbar-dark bg-dark">
    <div class="container-fluid">
      <span class="navbar-brand m-1 mb-0 h1">
        <img src="../assets/marshmallow_light.svg" alt="" height="20" />
        <router-link
          class="m-1"
          to="/"
          style="text-decoration: none; color: inherit"
          >MeUmy的棉花糖</router-link
        >
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
      this.$router.push({ path: "/" });
    },
    goBack() {
      this.$router.go(-1);
    },
    contactAdmin() {
      window.open("https://space.bilibili.com/674421433");
    },
  },
  beforeCreate() {
    if (this.withHomepageBtn) {
    }
  },
};
</script>