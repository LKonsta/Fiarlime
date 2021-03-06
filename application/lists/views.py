from flask import render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user
from sqlalchemy.sql import text

from application import app, db
from application.lists.models import Armylist, Unit_Armylist, Unit_Armylistupdate
from application.lists.forms import ListsForm, New_UnitForm, EditListForm, EditUnitForm

from application.armydata.models import ArmyType, UnitType, Unit, UnitUpdates
from application.armydata.forms import ArmyTypeForm, UnitTypeForm, UnitForm, UpdateForm

from application.auth.models import User
from application.auth.views import LoginForm


@app.route("/lists", methods=["GET"])
def lists_index():
    return render_template(
        "lists/list.html",
        lists=Armylist.query.all(),
        account=User.query.all(),
        armies=ArmyType.query.all()
    )


@app.route("/lists/show/<list_id>", methods=["GET"])
def lists_show_list(list_id):
    list_id = list_id
    army_id = Armylist.query.filter_by(id=list_id).first().army_type_id
    return render_template(
        "lists/show.html",
        list=Armylist.query.filter_by(id=list_id).first(),
        unitsinlist=Unit_Armylist.query.filter_by(Armylist_id=list_id).all(),
        unittype=UnitType.query.filter_by(ArmyType_id=army_id).all(),
    )


@app.route("/lists/delete/<list_id>", methods=["POST"])
@login_required
def list_remove(list_id):
    list_id = list_id
    army_list = Armylist.query.filter_by(id=list_id).first()
    if not current_user.id == army_list.account_id:
        abort(404)
    db.session().delete(army_list)
    db.session().commit()

    return redirect(url_for("lists_index"))


@app.route("/lists/my", methods=["GET"])
@login_required
def lists_user_lists():
    return render_template(
        "lists/userlists.html",
        lists=Armylist.query.filter_by(account_id=current_user.id).all(),
        armies=ArmyType.query.all()
    )


@app.route("/lists/new/")
@login_required
def lists_form():
    form = ListsForm()
    form.army_type_id.choices = [(str(army.id), army.name) for army in ArmyType.query.all()]

    return render_template(
        "lists/new.html",
        form=form,
        armies=ArmyType.query.all(),
        unittypes=UnitType.query.all(),
        units=Unit.query.all()
    )


@app.route("/lists/edit/<list_id>/<uil_id>", methods=["POST"])
@login_required
def list_remove_unit(list_id, uil_id):
    army_list = Armylist.query.filter_by(id=list_id).first()
    if not current_user.id == army_list.account_id:
        abort(404)
    ual = Unit_Armylist.query.get(uil_id)
    db.session().delete(ual)
    db.session().commit()

    return redirect(url_for("lists_edit", list_id=list_id))


@app.route("/lists/", methods=["POST"])
@login_required
def lists_create():
    form = ListsForm(request.form)
    form.army_type_id.choices = [(str(a.id), a.name) for a in ArmyType.query.all()]

    if not form.validate():
        return render_template("lists/new.html",
                               form=form,
                               armies=ArmyType.query.all()
                               )

    l = Armylist(form.name.data, form.points.data)

    l.army_type_id = form.army_type_id.data
    l.points = form.points.data
    l.account_id = current_user.id

    db.session().add(l)
    db.session().commit()

    return redirect(url_for("lists_edit", list_id=l.id))


@app.route("/lists/edit/<list_id>", methods=["GET", "POST"])
@login_required
def lists_edit(list_id):
    list_id = list_id
    army_list = Armylist.query.get(list_id)
    if not current_user.id == army_list.account_id:
        abort(404)
    army_id = army_list.army_type_id
    form = EditListForm(request.form)
    form.name.data = army_list.name
    form.points.data = army_list.points

    if request.method == "POST" and form.validate():
        army_list.name = request.form.get("name")
        army_list.points = request.form.get("points")

        db.session().commit()

        return redirect(url_for("lists_show_list", list_id=list_id))

    return render_template(
        "lists/edit.html",
        list=army_list,
        unitsinlist=Unit_Armylist.query.filter_by(Armylist_id=list_id).all(),
        unittype=UnitType.query.filter_by(ArmyType_id=army_id).all(),
        form=form
    )


@app.route("/lists/edit/<list_id>/edit/<unittype_id>/<uil_id>", methods=["GET", "POST"])
@login_required
def list_edit_unit(list_id, unittype_id, uil_id):
    army_list = Armylist.query.filter_by(id=list_id).first()
    nu = Unit_Armylist.query.get(uil_id)
    nu.Armylist_id = list_id
    if not current_user.id == army_list.account_id:
        abort(404)
    form = EditUnitForm(request.form)
    form.unit_id = nu.Unit_id
    list_id = list_id
    unittype_id = unittype_id
    uil_id = uil_id

    update_choices = UnitUpdates.query.filter_by(unit_id=nu.Unit_id).all()
    update_choise_list = [(
        str(upd.id),
        f"{upd.name} | {upd.cost} {'per/model' if upd.per else 'pts'}"
    ) for upd in update_choices]
    unit = Unit.query.filter_by(id=nu.Unit_id).first()
    if unit.default_updates:
        update_choise_list.append((str(1), 'Champion | 20'))
        update_choise_list.append((str(2), 'Musician | 20'))
        update_choise_list.append((str(3), 'Banner | 20'))
    form.updates.choices = update_choise_list

    if request.method == 'POST' and form.validate() and form.final.data:
        nu.amount = request.form.get("amount")
        for deletes in nu.updates:
            db.session().delete(deletes)
        this_unit = unit.query.filter_by(id=nu.Unit_id).first()
        if not this_unit.cost_per:
            totalcost = this_unit.start_cost
        else:
            extra = int(nu.amount) - this_unit.start_number
            totalcost = this_unit.start_cost + this_unit.cost_per * extra

        for ans in form.updates.data:
            this_update = UnitUpdates.query.filter_by(id=ans).first()
            if this_update.per:
                totalcost += this_update.cost * int(nu.amount)
            else:
                totalcost += this_update.cost
            update_to_unit_in_list = Unit_Armylistupdate()
            update_to_unit_in_list.unit_in_army_list = nu
            update_to_unit_in_list.update = this_update
            db.session().add(update_to_unit_in_list)

        nu.final_cost = totalcost

        db.session().commit()
        return redirect(url_for('lists_edit', list_id=list_id))

    form.amount.data = nu.amount

    return render_template(
        "lists/edit_unit.html",
        form=form,
        list_id=list_id,
        unittype_id=unittype_id,
        uil_id=uil_id,
        nu=nu
    )


nu = None


@app.route("/lists/edit/<list_id>/add/<unittype_id>", methods=["POST", "GET"])
@login_required
def list_add_unit(list_id, unittype_id):
    global nu
    army_list = Armylist.query.filter_by(id=list_id).first()
    if not current_user.id == army_list.account_id:
        abort(404)
    form = New_UnitForm(request.form)
    update_form = UpdateForm(request.form)
    list_id = list_id
    unittype_id = unittype_id
    unit_choices = Unit.query.filter_by(UnitType_id=unittype_id).all()
    form.unit.choices = [
        (
            str(unit.id),
            f"{unit.name} | {unit.start_cost} pts "
            f"{'+' + str(unit.cost_per) + ' pts/per extra' if unit.cost_per else ''} | "
            f"{'single model' if unit.max_amount == 1 else 'amount: ' + str(unit.start_number) + '-' + str(unit.max_amount)}"
        ) for unit in unit_choices
    ]
    if request.method == 'POST' and form.validate() and form.final.data:
        if nu == None:
            nu = Unit_Armylist(form.unit.data, form.amount.data)
            nu.Armylist_id = list_id

        this_unit = Unit.query.filter_by(id=form.unit.data).first()
        if not this_unit.cost_per:
            totalcost = this_unit.start_cost
        else:
            extra = form.amount.data - this_unit.start_number
            totalcost = this_unit.start_cost + this_unit.cost_per * extra

        for ans in update_form.updates.data:
            this_update = UnitUpdates.query.filter_by(id=ans).first()
            if this_update.per:
                totalcost += this_update.cost * form.amount.data
            else:
                totalcost += this_update.cost
            update_to_unit_in_list = Unit_Armylistupdate()
            update_to_unit_in_list.unit_in_army_list = nu
            update_to_unit_in_list.update = this_update
            db.session().add(update_to_unit_in_list)

        nu.final_cost = totalcost

        db.session().add(nu)
        db.session().commit()
        nu = None
        return redirect(url_for('lists_edit', list_id=list_id))

    if request.method == 'POST' and form.validate():
        nu = Unit_Armylist(form.unit.data, form.amount.data)
        nu.Armylist_id = list_id


        update_choices = UnitUpdates.query.filter_by(unit_id=form.unit.data).all()
        update_choise_list = [(
            str(upd.id),
            f"{upd.name} | {upd.cost} {'per/model' if upd.per else 'pts'}"
        ) for upd in update_choices]
        unit = Unit.query.filter_by(id=form.unit.data).first()
        if unit.default_updates:
            update_choise_list.append((str(1), 'Champion | 20'))
            update_choise_list.append((str(2), 'Musician | 20'))
            update_choise_list.append((str(3), 'Banner | 20'))
        update_form.updates.choices = update_choise_list

        return render_template(
            'lists/new_unit.html',
            form=form,
            update_form=update_form,
            list_id=list_id,
            unittype_id=unittype_id,
            unit_id=form.unit.data
        )

    return render_template(
        "lists/new_unit.html",
        form=form,
        list_id=list_id,
        unittype_id=unittype_id
    )
