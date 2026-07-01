/**
 * Propms workspace renderer — bypasses EditorJS (unreliable here) and draws
 * shortcuts/cards directly from get_desktop_page data.
 */
(function () {
	const LOG = "[propms-ws]";
	const PROPMS_WORKSPACES = new Set(["Property Management Solution", "PDC"]);

	function log(...args) {
		console.log(LOG, ...args);
	}

	function warn(...args) {
		console.warn(LOG, ...args);
	}

	function error(...args) {
		console.error(LOG, ...args);
	}

	function empty_page_data() {
		return {
			charts: { items: [] },
			shortcuts: { items: [] },
			cards: { items: [] },
			onboardings: { items: [] },
			quick_lists: { items: [] },
			number_cards: { items: [] },
			custom_blocks: { items: [] },
		};
	}

	function normalize_page_data(page_data) {
		if (!page_data || Array.isArray(page_data) || !page_data.cards) {
			return empty_page_data();
		}
		return page_data;
	}

	function summarize_page_data(page_data) {
		const summary = {};
		for (const key of Object.keys(page_data || {})) {
			const val = page_data[key];
			summary[key] = val?.items?.length ?? val;
		}
		return summary;
	}

	function resolve_current_page(pages, page) {
		if (!pages?.length || !page?.name) {
			return null;
		}
		return (
			pages.find((p) => p.title === page.name) ||
			pages.find((p) => p.name === page.name) ||
			pages.find((p) => frappe.router.slug(p.title) === frappe.router.slug(page.name)) ||
			null
		);
	}

	async function fetch_fresh_workspace_content(workspace_name) {
		try {
			const r = await frappe.db.get_value("Workspace", workspace_name, "content");
			const content = r?.message?.content;
			if (content) {
				return JSON.parse(content);
			}
		} catch (e) {
			warn("could not load fresh workspace content", e);
		}
		return null;
	}

	function destroy_editor(workspace) {
		if (!workspace.editor) {
			return;
		}
		try {
			workspace.editor.destroy?.();
		} catch (e) {
			/* ignore */
		}
		workspace.editor = null;
	}

	function ensure_editor_container(workspace) {
		if (!workspace.body.find("#editorjs")[0]) {
			workspace.body.find(".editor-js-container").append(
				`<div id="editorjs" class="desk-page page-main-content"></div>`
			);
		}
		return workspace.body.find("#editorjs");
	}

	function render_propms_workspace(workspace, page_data, title) {
		destroy_editor(workspace);
		const $container = ensure_editor_container(workspace);
		$container.empty().removeClass("hidden").show();

		const shortcuts = page_data.shortcuts?.items || [];
		const cards = page_data.cards?.items || [];

		log("rendering widgets", {
			title,
			shortcuts: shortcuts.length,
			cards: cards.length,
		});

		const $layout = $('<div class="propms-workspace-layout"></div>').appendTo($container);

		if (title) {
			$(
				`<div class="workspace-block col-xs-12" style="margin-bottom:12px"><h4 class="ellipsis" title="${frappe.utils.escape_html(
					title
				)}"><b>${frappe.utils.escape_html(__(title))}</b></h4></div>`
			).appendTo($layout);
		}

		if (shortcuts.length) {
			const $row = $('<div class="row widget-row"></div>').appendTo($layout);
			const $col = $('<div class="col-xs-12"></div>').appendTo($row);
			new frappe.widget.WidgetGroup({
				container: $col,
				type: "shortcut",
				columns: 3,
				height: null,
				widgets: shortcuts,
				options: { allow_sorting: false, allow_create: false, allow_delete: false },
			});
		}

		if (cards.length) {
			const $row = $('<div class="row widget-row"></div>').appendTo($layout);
			const col_size = Math.max(3, Math.floor(12 / Math.min(cards.length, 4)));
			cards.forEach((card) => {
				if (!card?.links?.length) {
					return;
				}
				const $col = $(`<div class="col-sm-6 col-md-${col_size}"></div>`).appendTo($row);
				new frappe.widget.SingleWidgetGroup({
					container: $col[0],
					type: "links",
					widgets: card,
					options: { allow_sorting: false, allow_create: false, allow_delete: false },
				});
			});
		}

		if (!shortcuts.length && !cards.length) {
			$layout.append(`
				<div class="text-muted" style="padding:20px">
					${__(
						"No workspace items are visible for your user roles. Please ask your administrator to assign the <b>Property Manager</b> or <b>Accounts Manager</b> role, and ensure the Property Management module is not blocked on your user."
					)}
				</div>
			`);
		}
	}

	function patch_workspace() {
		if (!window.frappe?.views?.Workspace || frappe.views.Workspace.prototype._propms_patched) {
			return false;
		}

		const Workspace = frappe.views.Workspace;
		log("applying propms workspace patch (widget renderer)");

		Workspace.prototype.add_custom_cards_in_content = function () {};

		const _get_data = Workspace.prototype.get_data;
		Workspace.prototype.get_data = function (page) {
			return _get_data.call(this, page).then((result) => {
				log("get_data", page?.title, summarize_page_data(this.page_data));
				return result;
			});
		};

		Workspace.prototype.show_page = async function (page) {
			if (!this.all_pages?.length) {
				warn("all_pages empty");
				return;
			}

			this.create_page_skeleton();

			try {
				const pages =
					page.public && this.public_pages.length
						? this.public_pages
						: this.private_pages;
				const current_page = resolve_current_page(pages, page);

				if (!current_page) {
					error("workspace page not found", page);
					return;
				}

				this._page = current_page;
				log("show_page", current_page.title);

				$(".item-anchor").addClass("disable-click");

				if (this.pages?.[current_page.name]) {
					this.page_data = this.pages[current_page.name];
				} else {
					await this.get_data(current_page);
				}

				this.page_data = normalize_page_data(this.page_data);

				if (PROPMS_WORKSPACES.has(current_page.title)) {
					const fresh = await fetch_fresh_workspace_content(current_page.name);
					if (fresh?.length) {
						log("fresh DB content blocks", fresh.length);
					}
					render_propms_workspace(this, this.page_data, current_page.title);
				} else {
					// Non-propms pages: keep core EditorJS path but await data properly
					this.content =
						(await fetch_fresh_workspace_content(current_page.name)) ||
						JSON.parse(current_page.content || "[]");
					if (this.pages?.[current_page.name]) {
						this.page_data = this.pages[current_page.name];
					} else {
						await this.get_data(current_page);
					}
					this.page_data = normalize_page_data(this.page_data);
					this.setup_actions(page);
					Workspace.prototype.prepare_editorjs.call(this);
				}

				this.setup_actions(page);
			} catch (err) {
				error("show_page failed", err);
			} finally {
				$(".item-anchor").removeClass("disable-click");
				this.remove_page_skeleton();
			}
		};

		Workspace.prototype._propms_patched = true;

		if (frappe.workspace?.show) {
			frappe.workspace.show();
		}

		return true;
	}

	log("script loaded");
	$(document).on("app_ready", () => patch_workspace());
	setTimeout(() => patch_workspace(), 0);
	setTimeout(() => patch_workspace(), 1000);
})();
