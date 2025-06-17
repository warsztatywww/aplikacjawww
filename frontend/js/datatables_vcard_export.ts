import VCard from 'vcard-creator';

export function vcard_export(e, dt, button, config) {
    const exportInfo = dt.buttons.exportInfo({...config, filename: '*', extension: '.vcf'});

    const columnRoles = dt.columns().indexes().map(function (idx) {
		const column = dt.column(idx);
        const columnName = column.header().innerText;
        const columnType = dt.settings()[0].aoColumns[idx].sType; // how the hell does the API not have a proper method to fetch this (https://datatables.net/forums/discussion/46910/getting-column-type-via-api)
        if (columnName == "Imię i nazwisko")
            return "name";
        if (columnName == "Email")
            return "email";
        if (columnType == "phoneNumber")
            return "phoneNumber";
		return null;
	}).toArray();

    const columnName = columnRoles.indexOf("name");
    const columnEmail = columnRoles.indexOf("email");
    // Get all phone number columns
    const columnPhone = columnRoles.map((role, i) => role === 'phoneNumber' ? i : -1).filter(index => index !== -1);
    
    // Get the description column for emergency contact phone
    const emergencyDescriptionColumn = dt.columns().indexes().map(function (idx) {
        const column = dt.column(idx);
        const columnName = column.header().innerText;
        return columnName.includes  ("Do kogo jest powyższy numer?") ? idx : -1;
    }).toArray().filter(index => index !== -1)[0];

    const data = dt.buttons.exportData().body;

    const vcards = data.map(function(row) {
        const vcard = new VCard();

        if (columnName !== -1 && row[columnName]) {
            const [firstName, lastName] = row[columnName].split(' ', 2); // TODO: this is stored as firstName and lastName in the db, find a better way to get this in JS...
            vcard.addName(firstName, lastName);
        }

        if (columnEmail !== -1 && row[columnEmail]) {
            vcard.addEmail(row[columnEmail]);
        }

        // Handle phone numbers with labels
        columnPhone.forEach((columnIdx, idx) => {
            if (row[columnIdx]) {
                const number = row[columnIdx];
                const columnName = dt.column(columnIdx).header().innerText;
                
                // Determine the appropriate label based on column name or index
                let phoneLabel = "WWW własny"; // Default label for participant's phone
                
                // If it's an emergency phone, get its description if available
                if (columnName.includes("awaryjn") && emergencyDescriptionColumn !== -1 && row[emergencyDescriptionColumn]) {
                    // Use the description from the emergency contact description column
                    phoneLabel = `WWW awaryjny(${row[emergencyDescriptionColumn]})`;
                } else if (columnName.includes("awaryjn")) {
                    phoneLabel = "WWW awaryjny";
                }
                
                // Use the hack to add the labeled phone number
                // This hack is needed because X-ABLabel is not directly exposed in the library 
                // and the 'phoneNumber' argument is only a sanity check
                vcard.setProperty(
                  'phoneNumber',
                  `item${idx+1}.TEL`,
                  `${number}`
                );
                vcard.setProperty(
                  'phoneNumber',
                  `item${idx+1}.X-ABLabel`,
                  phoneLabel
                );
            }
        });

        if (exportInfo.title) {
            vcard.addCompany(exportInfo.title);
            vcard.addNote(exportInfo.title);
        }

        return vcard.toString();
    });

    const result = vcards.join('\r\n');

    $.fn.dataTable.fileSave(
        new Blob( [result]),
        exportInfo.filename
    );
}