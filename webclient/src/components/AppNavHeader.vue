<template>
  <header class="navbar">
    <div class="container grid-lg">
      <div class="columns">
        <div class="column hide-lg">
          <RouterLink to="/">
            <img :alt="$t('meta.logo_alt')" src="@/assets/logos/navigatum.svg" id="logo" />
            <!-- 7px for logo1 -->
          </RouterLink>
        </div>
        <div class="column col-8 col-lg-11 col-mx-auto">
          <slot />
        </div>
      </div>
    </div>
  </header>
</template>

<style lang="scss">
@import "@/assets/variables";

.navbar {
  padding: 10px 0;
  box-shadow: 0 2px 3px $header-shadow-color;
  width: 100%;
  position: fixed;
  background: $header-color;
  top: 0;
  z-index: 2000;

  #logo {
    height: 24px;
    margin-top: 9px;
  }

  .input-group button {
    border: 0;
  }
}
</style>
