import { Component } from '@angular/core';

// Add the RxJS Observable operators we need in this app.
import './rxjs-operators';

@Component({
  selector: 'fatman-app',
  template: `
    <nav class="navbar navbar-inverse navbar-static-top">
      <div class="container-fluid">
        <div class="navbar-header">
          <button type="button" class="navbar-toggle collapsed" data-toggle="collapse"
            data-target="#main-navbar" aria-expanded="false">
          <span class="sr-only">Toggle navigation</span>
          <span class="icon-bar"></span>
          <span class="icon-bar"></span>
          <span class="icon-bar"></span>
          </button>
          <a class="navbar-brand" href="#">{{title}}</a>
        </div>
        <div id="main-navbar" class="collapse navbar-collapse">
          <ul class="nav navbar-nav">
            <li><a routerLink="/home" routerLinkActive="active">Home</a></li>
            <li><a routerLink="/tasks" routerLinkActive="active">Tasks</a></li>
            <li><a routerLink="/reports" routerLinkActive="active">Reports</a></li>
            <li><a routerLink="/machinestatus" routerLinkActive="active">Machine Status</a></li>
            <li><a routerLink="/periodictable/3/72" routerLinkActive="active">Periodic Table</a></li>
            <li><a routerLink="/methodlist" routerLinkActive="active">Method Overview</a></li>
            <li><a routerLink="/pseudos" routerLinkActive="active">Pseudos</a></li>
          </ul>
        </div> <!--/.navbar-collapse -->
      </div>
    </nav>
    <div class="container-fluid">
      <router-outlet></router-outlet>
    </div>
  `,
})

export class AppComponent {
  title = 'FATMAN';
}
