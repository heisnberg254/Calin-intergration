// Copyright (c) 2026, edwin@upande.com and contributors
// For license information, please see license.txt

frappe.ui.form.on('Water Meter', {
    refresh(frm) {
        if (frm.is_new()) return;

        const label = frm.doc.house_number ? __('Reassign House Number') : __('Assign House Number');
        frm.add_custom_button(label, () => {
            frappe.prompt(
                [
                    {
                        fieldname: 'context_html',
                        fieldtype: 'HTML',
                        options: `<p>Customer: <b>${frappe.utils.escape_html(frm.doc.calin_customer_id || '—')}</b>
                            &middot; Site: <b>${frappe.utils.escape_html(frm.doc.site || '—')}</b></p>`
                    },
                    {
                        fieldname: 'house_number',
                        label: __('House Number'),
                        fieldtype: 'Data',
                        reqd: 1,
                        default: frm.doc.house_number || ''
                    }
                ],
                (values) => {
                    frappe.call({
                        method: 'upande_hydrax.upande_hydrax.api.assign_house_number',
                        args: {
                            meter_id: frm.doc.name,
                            house_number: values.house_number
                        },
                        freeze: true,
                        freeze_message: __('Assigning house number...'),
                        callback: () => {
                            frappe.show_alert({ message: __('House number assigned'), indicator: 'green' });
                            frm.reload_doc();
                        }
                    });
                },
                __('Assign House Number'),
                __('Assign')
            );
        });
    }
});
