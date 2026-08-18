<template>
  <div class="auth-shell">
    <header class="auth-shell__topbar">
      <RouterLink to="/" class="auth-shell__wordmark" aria-label="返回衍界首页">
        <span class="auth-shell__mark" aria-hidden="true"><i /><i /><i /></span>
        <span>衍界 <em>YANJIE</em></span>
      </RouterLink>
      <span class="auth-shell__mode">PERSONAL DECISION COACH</span>
    </header>
    <main class="auth-shell__frame">
      <aside class="auth-shell__story" aria-label="衍界决策教练">
        <p class="auth-shell__kicker">MAKE THE NEXT MOVE CLEAR</p>
        <h2>把犹豫变成<br /><strong>可执行的判断。</strong></h2>
        <p class="auth-shell__intro">衍界帮你看清选择背后的条件、分支与下一步行动。</p>
        <div class="auth-shell__path" aria-hidden="true">
          <div class="auth-shell__path-line" />
          <div class="auth-shell__node auth-shell__node--start"><span>现在</span></div>
          <div class="auth-shell__node auth-shell__node--choice"><span>判断</span></div>
          <div class="auth-shell__node auth-shell__node--move"><span>行动</span></div>
          <div class="auth-shell__branch auth-shell__branch--one" />
          <div class="auth-shell__branch auth-shell__branch--two" />
        </div>
        <div class="auth-shell__signals">
          <div><b>01</b><span>看见关键约束</span></div>
          <div><b>02</b><span>比较可选路径</span></div>
          <div><b>03</b><span>推进下一步</span></div>
        </div>
      </aside>
      <section class="auth-shell__form-panel">
        <div class="auth-shell__form-inner">
          <div class="auth-shell__mobile-intro"><p>YANJIE / PERSONAL DECISION COACH</p></div>
          <div class="auth-shell__heading"><slot name="title" /><slot name="subtitle" /></div>
          <slot name="form" />
          <slot name="footer" />
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.auth-shell { --auth-line: rgba(174,215,235,.18); --auth-muted:#a8c0ce; position:relative; min-height:100dvh; overflow:hidden; isolation:isolate; color:#edf5fa; background:rgba(4,9,15,.12); font-family:'Avenir Next','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif; }
.auth-shell::before { position:absolute; z-index:0; inset:0; content:''; opacity:.6; pointer-events:none; background-image:linear-gradient(rgba(163,215,237,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(163,215,237,.04) 1px,transparent 1px); background-size:44px 44px; mask-image:linear-gradient(90deg,#000,transparent 72%); }
.auth-shell__topbar { position:absolute; top:0; right:0; left:0; z-index:2; display:flex; align-items:center; justify-content:space-between; max-width:1440px; margin:auto; padding:28px 42px; }
.auth-shell__wordmark { display:inline-flex; align-items:center; gap:10px; color:#f3fbff; font-family:'Songti SC','STSong','Noto Serif CJK SC',serif; font-weight:600; font-size:18px; line-height:1; text-decoration:none; }
.auth-shell__wordmark em { margin-left:5px; color:#77e7e8; font-family:'Avenir Next','Helvetica Neue',sans-serif; font-weight:500; font-size:9px; font-style:normal; letter-spacing:.18em; }
.auth-shell__mark { display:grid; width:26px; height:26px; grid-template-columns:repeat(3,1fr); align-items:end; gap:3px; border:1px solid rgba(120,231,232,.6); padding:4px; background:rgba(99,214,219,.08); }
.auth-shell__mark i { display:block; background:#71e2e1; }.auth-shell__mark i:nth-child(1){height:36%;opacity:.55}.auth-shell__mark i:nth-child(2){height:68%;opacity:.78}.auth-shell__mark i:nth-child(3){height:100%}
.auth-shell__mode { color:rgba(180,207,220,.6); font-size:10px; letter-spacing:.14em; }
.auth-shell__frame { position:relative; z-index:1; display:grid; min-height:100dvh; grid-template-columns:minmax(0,1.12fr) minmax(480px,.88fr); }
.auth-shell__story { position:relative; display:flex; min-height:720px; flex-direction:column; justify-content:center; padding:112px clamp(44px,8vw,140px) 58px; overflow:hidden; }
.auth-shell__story::before { position:absolute; top:0; right:-26%; width:76%; height:100%; content:''; opacity:.72; background:linear-gradient(115deg,transparent 30%,rgba(31,111,125,.19)); transform:skewX(-17deg); }
.auth-shell__kicker,.auth-shell__mobile-intro p { z-index:1; margin:0 0 20px; color:#74dfe1; font-family:'SFMono-Regular','Cascadia Mono','Noto Sans Mono',monospace; font-size:10px; letter-spacing:.18em; }
.auth-shell__story h2 { z-index:1; margin:0; color:#eaf6f9; font-family:'Songti SC','STSong','Noto Serif CJK SC',serif; font-weight:400; font-size:clamp(38px,4vw,64px); line-height:1.17; }.auth-shell__story h2 strong{color:#86e5df;font-weight:400}
.auth-shell__intro { z-index:1; max-width:380px; margin:24px 0 0; color:#a0b6c5; font-size:15px; line-height:1.9; }
.auth-shell__path { position:relative; z-index:1; width:min(430px,76%); height:170px; margin-top:36px; }.auth-shell__path-line,.auth-shell__branch { position:absolute; height:1px; transform-origin:left center; }.auth-shell__path-line{top:50%;left:3%;width:85%;background:linear-gradient(90deg,#59869b,#75e4de 64%,transparent)}.auth-shell__branch{left:62%;width:32%;background:rgba(119,226,225,.48)}.auth-shell__branch--one{top:50%;transform:rotate(-28deg)}.auth-shell__branch--two{top:50%;transform:rotate(31deg)}
.auth-shell__node { position:absolute; top:calc(50% - 7px); width:14px; height:14px; border:2px solid #8ee8e4; border-radius:50%; background:#0c1822; box-shadow:0 0 0 6px rgba(112,224,220,.08); }.auth-shell__node span{position:absolute;top:22px;left:50%;color:#b7cad5;font-size:11px;white-space:nowrap;transform:translateX(-50%)}.auth-shell__node--start{left:1%}.auth-shell__node--choice{left:37%}.auth-shell__node--move{left:60%;background:#86e5df;box-shadow:0 0 0 6px rgba(112,224,220,.13),0 0 24px rgba(114,225,220,.56)}
.auth-shell__signals { z-index:1; display:flex; flex-wrap:wrap; gap:16px 30px; margin-top:22px; }.auth-shell__signals div{display:flex;align-items:center;gap:8px;color:#a4bac7;font-size:12px}.auth-shell__signals b{color:#70e1df;font-family:ui-monospace,monospace;font-size:10px;font-weight:500}
.auth-shell__form-panel { display:flex; min-height:100%; align-items:center; justify-content:center; border-left:1px solid var(--auth-line); background:rgba(7,15,25,.62); box-shadow:-28px 0 64px rgba(1,5,10,.24); }.auth-shell__form-inner{box-sizing:border-box;width:min(100%,430px);padding:118px 42px 54px}.auth-shell__mobile-intro{display:none}
.auth-shell__heading :deep(h1) { margin:0; color:#f2f9fb; font-family:'Songti SC','STSong','Noto Serif CJK SC',serif; font-size:36px; font-weight:400; line-height:1.2; }.auth-shell__heading :deep(p){margin:11px 0 0;color:var(--auth-muted);font-size:14px;line-height:1.85}
:deep(.auth-form){display:grid;gap:17px;margin-top:34px}:deep(.auth-field){display:grid;gap:8px}:deep(.auth-field__label){display:flex;justify-content:space-between;color:#c0d0d8;font-family:'SFMono-Regular','Cascadia Mono','Noto Sans Mono',monospace;font-size:11px;letter-spacing:.035em}:deep(.auth-field__hint){color:#718a99;font-family:'Avenir Next','PingFang SC',sans-serif;font-size:11px;letter-spacing:0}:deep(.auth-input-wrap){position:relative}
:deep(.auth-input){width:100%;min-height:48px;border:1px solid rgba(159,197,212,.16);border-radius:7px;outline:none;padding:0 14px;color:#ebf6f8;background:rgba(158,202,222,.045);font-family:'Avenir Next','PingFang SC','Microsoft YaHei',sans-serif;font-size:14px;letter-spacing:.01em;transition:border-color 160ms ease,background 160ms ease,box-shadow 160ms ease}:deep(.auth-input--with-action){padding-right:48px}:deep(.auth-input::placeholder){color:#506978}:deep(.auth-input:hover){border-color:rgba(159,222,225,.3)}:deep(.auth-input:focus){border-color:#79dfdf;background:rgba(94,190,196,.08);box-shadow:0 0 0 3px rgba(95,215,214,.1)}
:deep(.auth-icon-button){position:absolute;top:50%;right:9px;display:grid;width:30px;height:30px;place-items:center;border:0;border-radius:5px;padding:0;color:#9cc3ca;background:transparent;cursor:pointer;transform:translateY(-50%)}:deep(.auth-icon-button:hover){color:#8ee8e4;background:rgba(110,226,223,.1)}:deep(.auth-eye){position:relative;display:block;width:17px;height:11px;border:1.5px solid currentColor;border-radius:100% 0;transform:rotate(45deg)}:deep(.auth-eye::after){position:absolute;top:50%;left:50%;width:4px;height:4px;border-radius:50%;content:'';background:currentColor;transform:translate(-50%,-50%)}:deep(.auth-eye--closed::before){position:absolute;top:4px;left:-3px;width:20px;height:1.5px;content:'';background:currentColor;transform:rotate(-45deg)}
:deep(.auth-error){margin:2px 0 0;border-left:2px solid #ef8585;padding:9px 11px;color:#ffc6c6;background:rgba(190,65,65,.1);font-size:12px;line-height:1.55}:deep(.auth-footer){margin:27px 0 0;color:#829aa8;font-size:13px;text-align:center}:deep(.auth-footer a){color:#81e2df;text-underline-offset:4px}:deep(.auth-footer a:hover){color:#c7ffff}
@media (max-width:860px){.auth-shell__topbar{padding:22px 24px}.auth-shell__mode{display:none}.auth-shell__frame{display:block}.auth-shell__story{display:none}.auth-shell__form-panel{min-height:100dvh;border:0;background:rgba(4,11,18,.5);box-shadow:none}.auth-shell__form-inner{padding:112px 24px 42px}.auth-shell__mobile-intro{display:block}.auth-shell__mobile-intro p{margin-bottom:15px;font-size:9px}}@media (max-width:420px){:deep(.auth-field__label){display:grid;gap:3px}:deep(.auth-field__hint){text-align:left}}@media (max-width:380px){.auth-shell__form-inner{padding-right:18px;padding-left:18px}.auth-shell__topbar{padding-right:18px;padding-left:18px}}
</style>
