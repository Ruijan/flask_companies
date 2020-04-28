
class DivergingHierarchicalBarChart extends VerticalBarChart{
    constructor(container_name, data) {
        super(container_name, data, ({top: 30, right: 30, bottom: 30, left: 30}));
    }

    init(){
        this.duration = 500
    }

    transformData(data){
        return d3.hierarchy(data)
            .sort((a, b) => b.value - a.value)
            .eachAfter(d => d.index = d.parent ? d.parent.index = d.parent.index + 1 || 0 : 0)
    }

    computeMaxXDomain() {
        return this.root.value;
    }

    buildSVG(){
        this.center = Math.round(this.width / 2);
        this.color = d3.scaleOrdinal([0, 1, 2], ["red", "steelblue", "#aaa"])

        this.svg = this.container.append("svg")
            .attr("preserveAspectRatio", "xMinYMin meet")
            .attr("viewBox", "0 0 " + this.width + " " + this.height);
        this.svg.append("rect")
            .attr("class", "background")
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .attr("width", this.width)
            .attr("height", this.height)
            .attr("cursor", "pointer")
            .on("click", d => this.up(d));
        this.xAxis = g => g
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${this.margin.top})`)
            .call(d3.axisTop(this.x).ticks(this.width / 80, "s"))
            .call(g => (g.selection ? g.selection() : g).select(".domain").remove())
        this.yAxis = g => g
            .attr("class", "y-axis")
            .attr("transform", `translate(${this.center + 1},0)`)
            .call(g => g.append("line")
                .attr("stroke", "currentColor")
                .attr("y1", this.margin.top)
                .attr("y2", this.height - this.margin.bottom))
        this.svg.append("g")
            .call(this.xAxis);

        this.svg.append("g")
            .call(this.yAxis);
        this.down(this.root);
    }

    getHeight(){
        let max = 1;
        this.root.each(d => d.children && (max = Math.max(max, d.children.length)));
        return max * this.barStep + this.margin.top + this.margin.bottom;
    }

    up(d) {
        if (!d.parent || !this.svg.selectAll(".exit").empty()) return;

        // Rebind the current node to the background.
        this.svg.select(".background").datum(d.parent);

        // Define two sequenced transitions.
        const transition1 = this.svg.transition().duration(this.duration);
        const transition2 = transition1.transition();

        // Mark any currently-displayed bars as exiting.
        const exit = this.svg.selectAll(".enter")
            .attr("class", "exit");

        // Update the x-scale domain.
        let minimum = Math.abs(d3.min(d.parent.children, d => d.value))
        let maximum = Math.abs(d3.max(d.parent.children, d => d.value))
        maximum = maximum > minimum ? maximum : minimum;
        this.x.domain([-maximum * 1.1, +maximum * 1.1]);

        // Update the x-axis.
        this.svg.selectAll(".x-axis").transition(transition1)
            .call(this.xAxis);

        // Transition exiting bars to the new x-scale.
        exit.selectAll("g").transition(transition1)
            .attr("transform", stagger(this.x, this.barStep));

        // Transition exiting bars to the parent’s position.
        exit.selectAll("g").transition(transition2)
            .attr("transform", stack(d.index, this.x, this.barStep));

        // Transition exiting rects to the new scale and fade to parent color.
        exit.selectAll("rect").transition(transition1)
            .attr("width", d => getWidth(d.value, this.x))
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0));

        // Transition exiting text to fade out.
        // Remove exiting nodes.
        exit.transition(transition2)
            .attr("fill-opacity", 0)
            .remove();

        // Enter the new bars for the clicked-on data's parent.
        const enter = this.createBar(d.parent, ".exit")
            .attr("fill-opacity", 0);

        // Transition entering bars to the new x-scale.
        enter.selectAll("g").transition(transition2)
            .attr("transform", (d, i) => `translate(${getXPos(d.value, this.x, 0)} ,${this.barStep * i})`)
        enter.selectAll("text")
            .attr("transform", (d, i) => `translate(${-getXPos(d.value, this.x, 0)},0)`);

        // Transition entering bars to fade in over the full duration.
        enter.transition(transition2)
            .attr("fill-opacity", 1);

        // Color the bars as appropriate.
        // Exiting nodes will obscure the parent bar, so hide it.
        // Transition entering rects to the new x-scale.
        // When the entering parent rect is done, make it visible!
        enter.selectAll("rect")
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0))
            .attr("fill-opacity", p => p === d ? 0 : null)
            .transition(transition2)
            .attr("width", d => getWidth(d.value, this.x))
            .on("end", function(p) { d3.select(this).attr("fill-opacity", 1); });
    }

    down(d) {
        if (!d.children || d3.active(this.svg.node())) return;

        // Rebind the current node to the background.
        this.svg.select(".background").datum(d);

        // Define two sequenced transitions.
        const transition1 = this.svg.transition().duration(this.duration);
        const transition2 = transition1.transition();

        // Mark any currently-displayed bars as exiting.
        const exit = this.svg.selectAll(".enter")
            .attr("class", "exit");

        // Entering nodes immediately obscure the clicked-on bar, so hide it.
        exit.selectAll("rect")
            .attr("fill-opacity", p => p === d ? 0 : null);

        // Transition exiting bars to fade out.
        exit.transition(transition1)
            .attr("fill-opacity", 0)
            .remove();

        // Enter the new bars for the clicked-on data.
        // Per above, entering bars are immediately visible.
        const enter = this.createBar(d, ".y-axis")
            .attr("fill-opacity", 0);

        // Have the text fade-in, even though the bars are visible.
        enter.transition(transition1)
            .attr("fill-opacity", 1);

        // Transition entering bars to their new y-position.
        enter.selectAll("g")
            .attr("transform", stack(d.index, this.x, this.barStep))
            .transition(transition1)
            .attr("transform", stagger(this.x, this.barStep));

        // Update the x-scale domain.
        let minimum = Math.abs(d3.min(d.children, d => d.value));
        let maximum = Math.abs(d3.max(d.children, d => d.value));
        maximum = maximum > minimum ? maximum : minimum;
        this.x.domain([-maximum*1.1, +maximum*1.1]);

        // Update the x-axis.
        this.svg.selectAll(".x-axis").transition(transition2)
            .call(this.xAxis);

        // Transition entering bars to the new x-scale.
        enter.selectAll("g").transition(transition2)
            .attr("transform", (d, i) => `translate(${getXPos(d.value, this.x, 0)} ,${this.barStep * i})`)
        enter.selectAll("text")
            .attr("transform", (d, i) => `translate(${-getXPos(d.value, this.x, 0)},0)`);

        // Color the bars as parents; they will fade to children if appropriate.
        enter.selectAll("rect")
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0))
            .attr("fill-opacity", 1)
            .transition(transition2)
            .attr("fill", d => d.value > 0 ? this.color(1) : this.color(0))
            .attr("width", d => getWidth(d.value, this.x));
    }

    // Creates a set of bars for the given data node, at the specified index.
    createBar(d, selector) {
        let chart = this;
        const g = this.svg.insert("g", selector)
            .attr("class", "enter")
            .attr("transform", `translate(0,${this.margin.top + this.barStep * this.barPadding})`)
            .attr("text-anchor", "end")
            .style("font", "14px sans-serif").style('fill', 'cornsilk');

        const bar = g.selectAll("g")
            .data(d.children)
            .join("g")
            .attr("cursor", d => !d.children ? null : "pointer")
            .on("click", d => this.down(d));

        bar.append("text")
            .attr("x", (d) => d.value > 0 ? this.center - 6 : this.center + 6 )
            .attr("y", this.barStep * (1 - this.barPadding) / 2)
            .attr("dy", ".35em")
            .attr('text-anchor', (d) => d.value > 0 ? 'end' : 'start')
            .text(d => d.data.name).style('fill', 'cornsilk');

        // Three function that change the tooltip when user hover / move / leave a cell
        let mouseover = function(d) {
            chart.tooltip.style("opacity", 1)
        }
        let mousemove = function(d) {
            let tip = ""
            if(d.children != undefined){
                tip = "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Companies</span>: </td>" +
                    "<td style='text-align: right;'>" + getNumberOfChildren(d) + "</td></tr>" +
                    "<tr><td style='text-align: center; padding-left: 5px; padding-right: 5px; color: dodgerblue;' colspan='2'>Click on the bar to expand</td></tr>"
            }
            chart.tooltip
                .html("<table><tr><td style='text-align: left;'><span style='color: dodgerblue'>Name</span>: </td>" +
                    "<td style='text-align: right;'>" + d.data.name + "</td></tr>" +
                    "<tr><td style='text-align: left;'><span style='color: dodgerblue'>Amount</span>: </td>" +
                    "<td style='text-align: right;'>" + Math.round(d.value*100)/100 + "</td></tr>" +
                    tip +
                    "</table>")
                .style("top", (d3.event.pageY + 30)+"px")
                .style("left",(d3.event.pageX + 30)+"px")
        }
        let mouseleave = function(d) {
            chart.tooltip
                .style("opacity", 0)
        }
        bar.append("rect")
            .attr("x", this.center)
            .attr("width", d => getWidth(d.value, this.x))
            .attr("height", this.barStep * (1 - this.barPadding))
            .on('mouseenter', function (actual, i) {
                d3.select(this).attr('opacity', 0.5)
                bar.selectAll('#limit').remove()
                let pos_x = 0
                if(actual.value > 0){
                    pos_x = getXPos(actual.value, chart.x, chart.center) + getWidth(actual.value, chart.x);
                }
                else{
                    pos_x = getXPos(actual.value, chart.x, chart.center);
                }
                bar.append('line')
                    .attr('id', 'limit')
                    .attr('x1', (d) => pos_x + (d.value > 0 ? 0 : getWidth(d.value, chart.x)))
                    .attr('y1', 0)
                    .attr('x2', (d) => pos_x + (d.value > 0 ? 0 : getWidth(d.value, chart.x)))
                    .attr('y2', chart.barStep)
                    .attr('stroke', 'red')
                bar.append('text')
                    .attr('class', 'divergence')
                    .attr('x', (a) => a.value > 0 ? chart.x(a.value) + 6 : chart.x(a.value) + getWidth(a.value, chart.x) - 6)
                    .attr('y', (a) => chart.barStep * (1 - chart.barPadding) * 2 /3)
                    .attr('fill', 'white')
                    .attr('text-anchor', (a) => a.value > 0 ? 'start' : 'end')
                    .text((a, idx) => {
                        const divergence = ((a.value - actual.value)/actual.value * 100).toFixed(1)
                        let text = ''
                        if (divergence > 0) text += '+'
                        text += `${divergence}%`
                        return idx !== i ? text : '';
                    })
            })
            .on('mouseover', mouseover)
            .on('mouseleave', function (actual, i) {
                d3.select(this).attr('opacity', 1)
                bar.selectAll('#limit').remove()
                bar.selectAll('.divergence').remove()
                mouseleave(actual);
            })
            .on('mousemove',mousemove);

        return g;
    }
}

function getXPos(x, range, offset){
    let value = Math.min(0, -(range(0) - range(x))) + offset
    return value;
}

function getWidth(x, range){
    let value = Math.abs(range(x) - range(0))
    return value;
}

function stagger(x, barStep) {
    let negative_value = 0;
    let positive_value = 0;
    return (d, i) => {
        let t;
        if(d.value < 0){
            negative_value += d.value;
            t = `translate(${x(negative_value) - x(0)},${barStep * i})`;
        }
        //const t = `translate(${getXPos(value, x, 0)},${barStep * i})`;

        if(d.value > 0) {
            t = `translate(${x(positive_value) - x(0)},${barStep * i})`;
            positive_value += d.value;
        }
        return t;
    };
}

function stack(i, x, barStep) {
    let negative_value = 0;
    let positive_value = 0;
    return (d) => {
        let t;
        if(d.value < 0){
            negative_value += d.value;
            t = `translate(${x(negative_value) - x(0)},${barStep * i})`;
        }

        if(d.value > 0) {
            t = `translate(${x(positive_value) - x(0)},${barStep * i})`;
            positive_value += d.value;
        }
        return t;
    };
}

function getNumberOfChildren(n) {
    if (n.children == undefined) return 1;
    var nb_children = 0;
    n.children.forEach(function(c){
        nb_children += getNumberOfChildren(c);
    });
    return nb_children;
}





