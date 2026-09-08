# 論文のビルド

pLaTeX、pBibTeX、dvipdfmx、latexmk と、本文で使用する LaTeX パッケージが必要です。
このディレクトリで次を実行してください。

```sh
latexmk main.tex
```

`latexmkrc` は pBibTeX による参考文献生成と、引用を解決するための pLaTeX の再実行を設定しています。
`fikes1971planex` と `fox2006stability` は `references.bib` に登録済みです。
これらの引用が未定義のまま残る場合は、古い補助ファイルと参考文献出力を再生成してください。

```sh
latexmk -gg main.tex
```

latexmk を使用しない場合は、次の順序で実行してください。

```sh
platex main.tex
pbibtex main
platex main.tex
platex main.tex
dvipdfmx main.dvi
```

Overleaf ではメイン文書を `main.tex` に設定し、`Recompile from scratch` を実行してください。
`JY1/hmc/b/n` などのフォント置換メッセージは、引用の未定義とは別の問題です。
