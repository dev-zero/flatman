import { Component, Input, OnChanges, SimpleChange,  Pipe, PipeTransform } from '@angular/core';

import { Pseudo, PseudoFamily } from './pseudo';
import { PseudoService } from './pseudo.service';
import { PseudoTableElement } from './pseudo-table-element.component';

@Component({
  selector: 'pseudotable',
  templateUrl: 'pseudos/pseudo-table.component.html',
  styleUrls: ['pseudos/pseudo-table.component.css'],
  directives: [PseudoTableElement],
})

export class PseudoTable implements OnChanges {
  @Input()
  family: PseudoFamily;

  errorMessage: string;
  pseudos: { [element: string] : Pseudo } = {};

  constructor(private _pseudoService: PseudoService) { }

  getPseudos() {
    this.pseudos = {};

    if (this.family)
      this._pseudoService.getPseudos(this.family).subscribe(
        pseudos => {
          for (let pseudo of pseudos)
            this.pseudos[pseudo.element] = pseudo;
        },
        error   => this.errorMessage = <any>error);
  }

  ngOnChanges(changes: {[propertyName: string]: SimpleChange}) {
    if (changes['family'])
      this.getPseudos();
  }
}
